import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from common.permissions import screen_permission_required

logger = logging.getLogger('accounting')

from accounts.models import Account, JournalEntry, JournalEntryLine
from assets.models import Asset, DepreciationEntry
from bank_reconciliation.models import BankStatementItem
from budget.models import Budget, CostCenter
from cheques.models import Cheque
from common.excel_utils import export_to_excel
from common.pdf_utils import export_to_pdf
from hr.models import Employee, Salary
from purchases.models import Product, PurchaseInvoice, Supplier
from sales.models import Customer, SalesInvoice, SalesInvoiceLine
from tax_invoices.models import ETAConnection, TaxInvoice
from treasury.models import Bank, BankTransaction, Safe, SafeTransaction
from warehouses.models import InventoryCostLayer, StockMovement, Warehouse, WarehouseProduct


def _safe_parse_date(value, param_name=''):
    """تحليل تاريخ بأمان - يعيد None بدلاً من رمي استثناء."""
    if not value or not isinstance(value, str):
        return value
    try:
        return datetime.strptime(value.strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        logger.warning('Invalid date format for %s: %s', param_name, value)
        return None


def _validate_date_range(request, date_from, date_to):
    """التحقق من صحة نطاق التاريخ وإصلاحه إن أمكن."""
    if date_from and date_to and date_from > date_to:
        messages.warning(request, 'تاريخ البداية أحدث من تاريخ النهاية - تم تبادلهما تلقائياً')
        date_from, date_to = date_to, date_from
    return date_from, date_to


def _posted_lines_in_range(date_from, date_to):
    """تجميع مدين/دائن لبنود القيود المرحلة لكل حساب ضمن نطاق تاريخ اختياري.

    يعيد dict: {account_id: {'debit': Decimal, 'credit': Decimal}}
    """
    from accounts.models import JournalEntryLine

    qs = JournalEntryLine.objects.filter(journal_entry__is_posted=True)
    if date_from:
        qs = qs.filter(journal_entry__date__gte=date_from)
    if date_to:
        qs = qs.filter(journal_entry__date__lte=date_to)
    rows = qs.values('account_id').annotate(d=Sum('debit'), c=Sum('credit'))
    result = {}
    for r in rows:
        result[r['account_id']] = {'debit': r['d'] or Decimal('0'), 'credit': r['c'] or Decimal('0')}
    return result


def _period_net(activity, account_type):
    """صافي النشاط الدفتري للفترة بالإشارة الصحيحة حسب طبيعة الحساب.

    الأصول والمصروفات: رصيد مدين طبيعي (مدين - دائن)
    الخصوم وحقوق الملكية والإيرادات: رصيد دائن طبيعي (دائن - مدين)
    """
    debit = activity.get('debit', Decimal('0'))
    credit = activity.get('credit', Decimal('0'))
    if account_type in ('asset', 'expense'):
        return debit - credit
    return credit - debit


def _trial_balance_split(net, account_type):
    """توزيع الصافي على عمودي مدين/دائن حسب طبيعة الحساب."""
    debit = Decimal('0')
    credit = Decimal('0')
    if net == 0:
        return debit, credit
    if account_type in ('asset', 'expense'):
        if net > 0:
            debit = net
        else:
            credit = -net
    else:
        if net > 0:
            credit = net
        else:
            debit = -net
    return debit, credit


def _balances_as_of(accounts, as_of_date):
    """أرصدة الحسابات حتى تاريخ معين = الافتتاحي + حركة القيود المرحلة حتى التاريخ."""
    from accounts.models import JournalEntryLine

    ids = [a.pk for a in accounts]
    qs = (
        JournalEntryLine.objects.filter(
            journal_entry__is_posted=True, journal_entry__date__lte=as_of_date, account_id__in=ids
        )
        .values('account_id')
        .annotate(d=Sum('debit'), c=Sum('credit'))
    )
    agg = {r['account_id']: (r['d'] or Decimal('0')) - (r['c'] or Decimal('0')) for r in qs}
    balances = {}
    for acc in accounts:
        balances[acc.pk] = acc.opening_balance + agg.get(acc.pk, Decimal('0'))
    return balances


def _get_date_range(request, default_from=None, default_to=None):
    """جلب وتحليل نطاق التاريخ من query string بشكل آمن."""
    from django.contrib import messages as msg_module

    raw_from = request.GET.get('date_from')
    raw_to = request.GET.get('date_to')

    date_from = _safe_parse_date(raw_from, 'date_from')
    date_to = _safe_parse_date(raw_to, 'date_to')

    if raw_from and date_from is None:
        msg_module.warning(request, f'صيغة تاريخ البداية غير صحيحة: "{raw_from}". الصيغة المطلوبة: YYYY-MM-DD')
        date_from = default_from or timezone.now().date().replace(month=1, day=1)
    elif date_from is None:
        date_from = default_from or timezone.now().date().replace(month=1, day=1)

    if raw_to and date_to is None:
        msg_module.warning(request, f'صيغة تاريخ النهاية غير صحيحة: "{raw_to}". الصيغة المطلوبة: YYYY-MM-DD')
        date_to = default_to or timezone.now().date()
    elif date_to is None:
        date_to = default_to or timezone.now().date()

    date_from, date_to = _validate_date_range(request, date_from, date_to)
    return date_from, date_to


@login_required
@cache_page(120)
@vary_on_cookie
def dashboard_view(request):
    today = timezone.now().date()
    month_start = today.replace(day=1)

    total_purchases_month = PurchaseInvoice.objects.filter(date__gte=month_start, date__lte=today).aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')

    total_purchases_today = PurchaseInvoice.objects.filter(date=today).aggregate(total=Sum('total_amount'))[
        'total'
    ] or Decimal('0')

    total_sales_month = SalesInvoice.objects.filter(date__gte=month_start, date__lte=today).aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')

    total_sales_today = SalesInvoice.objects.filter(date=today).aggregate(total=Sum('total_amount'))[
        'total'
    ] or Decimal('0')

    total_profit_month = SalesInvoice.objects.filter(date__gte=month_start, date__lte=today).aggregate(
        profit=Sum('gross_profit')
    )['profit'] or Decimal('0')

    vat_output = SalesInvoice.objects.filter(date__gte=month_start, is_tax_invoice=True).aggregate(
        total=Sum('vat_amount')
    )['total'] or Decimal('0')

    vat_input = PurchaseInvoice.objects.filter(date__gte=month_start, is_tax_invoice=True).aggregate(
        total=Sum('vat_amount')
    )['total'] or Decimal('0')

    vat_net = vat_output - vat_input

    total_receivables = SalesInvoice.objects.filter(remaining_amount__gt=0).aggregate(total=Sum('remaining_amount'))[
        'total'
    ] or Decimal('0')

    total_payables = PurchaseInvoice.objects.filter(remaining_amount__gt=0).aggregate(total=Sum('remaining_amount'))[
        'total'
    ] or Decimal('0')

    suppliers_count = Supplier.objects.filter(is_active=True).count()
    customers_count = Customer.objects.filter(is_active=True).count()
    employees_count = Employee.objects.filter(status='active').count()
    products_count = Product.objects.filter(is_active=True).count()
    assets_count = Asset.objects.filter(status='active').count()

    banks = Bank.objects.filter(is_active=True)
    safes = Safe.objects.filter(is_active=True)
    total_bank_balance = banks.aggregate(total=Sum('current_balance'))['total'] or Decimal('0')
    total_safe_balance = safes.aggregate(total=Sum('current_balance'))['total'] or Decimal('0')

    recent_sales = SalesInvoice.objects.select_related('customer').order_by('-date')[:5]
    recent_purchases = PurchaseInvoice.objects.select_related('supplier').order_by('-date')[:5]

    overdue_count = SalesInvoice.objects.filter(remaining_amount__gt=0, due_date__lt=today, is_posted=True).count()
    overdue_ap_count = PurchaseInvoice.objects.filter(
        remaining_amount__gt=0, due_date__lt=today, is_posted=True
    ).count()

    from warehouses.models import WarehouseProduct

    low_stock_count = (
        WarehouseProduct.objects.filter(quantity__lte=F('minimum_quantity')).exclude(minimum_quantity=0).count()
    )

    profit_margin = 0
    if total_sales_month:
        profit_margin = round(total_profit_month / total_sales_month * 100, 1)

    chart_labels = []
    chart_sales = []
    chart_purchases = []
    month_ranges = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_start_c = today.replace(year=y, month=m, day=1)
        if m == 12:
            month_end_c = today.replace(year=y + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end_c = today.replace(year=y, month=m + 1, day=1) - timedelta(days=1)
        chart_labels.append(f'{m}/{y}')
        month_ranges.append((month_start_c, month_end_c))

    sales_by_month = {}
    for row in (
        SalesInvoice.objects.filter(is_posted=True, date__gte=month_ranges[0][0], date__lte=month_ranges[-1][1])
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(t=Sum('total_amount'))
    ):
        if row['month']:
            sales_by_month[(row['month'].year, row['month'].month)] = float(row['t'] or 0)

    purchases_by_month = {}
    for row in (
        PurchaseInvoice.objects.filter(is_posted=True, date__gte=month_ranges[0][0], date__lte=month_ranges[-1][1])
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(t=Sum('total_amount'))
    ):
        if row['month']:
            purchases_by_month[(row['month'].year, row['month'].month)] = float(row['t'] or 0)

    for ms, me in month_ranges:
        key = (ms.year, ms.month)
        chart_sales.append(sales_by_month.get(key, 0))
        chart_purchases.append(purchases_by_month.get(key, 0))

    top_suppliers_debt = Supplier.objects.filter(current_balance__gt=0).order_by('-current_balance')[:5]

    top_customers_debt = Customer.objects.filter(current_balance__gt=0).order_by('-current_balance')[:5]

    pending_approvals_pi = PurchaseInvoice.objects.filter(approved_by__isnull=True, is_posted=False).count()

    pending_approvals_si = SalesInvoice.objects.filter(approved_by__isnull=True, is_posted=False).count()

    recent_journal_entries = JournalEntry.objects.select_related('created_by').order_by('-date')[:5]

    context = {
        'today': today,
        'total_purchases_month': total_purchases_month,
        'total_purchases_today': total_purchases_today,
        'total_sales_month': total_sales_month,
        'total_sales_today': total_sales_today,
        'total_profit_month': total_profit_month,
        'vat_output': vat_output,
        'vat_input': vat_input,
        'vat_net': vat_net,
        'total_receivables': total_receivables,
        'total_payables': total_payables,
        'suppliers_count': suppliers_count,
        'customers_count': customers_count,
        'employees_count': employees_count,
        'products_count': products_count,
        'assets_count': assets_count,
        'total_bank_balance': total_bank_balance,
        'total_safe_balance': total_safe_balance,
        'banks': banks,
        'safes': safes,
        'recent_sales': recent_sales,
        'recent_purchases': recent_purchases,
        'low_stock_count': low_stock_count,
        'overdue_count': overdue_count,
        'overdue_ap_count': overdue_ap_count,
        'profit_margin': profit_margin,
        'chart_labels': chart_labels,
        'chart_sales': chart_sales,
        'chart_purchases': chart_purchases,
        'top_suppliers_debt': top_suppliers_debt,
        'top_customers_debt': top_customers_debt,
        'pending_approvals_pi': pending_approvals_pi,
        'pending_approvals_si': pending_approvals_si,
        'recent_journal_entries': recent_journal_entries,
    }
    return render(request, 'dashboard.html', context)


@screen_permission_required('reports.report', 'view')
@cache_page(300, key_prefix='fin_dash')
@vary_on_cookie
def financial_dashboard(request):
    """لوحة التحكم المالية الموحدة - تجمع المؤشرات المالية الرئيسية في شاشة واحدة"""
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # ── المركز النقدي ──
    banks = Bank.objects.filter(is_active=True)
    safes = Safe.objects.filter(is_active=True)
    total_bank_balance = banks.aggregate(total=Sum('current_balance'))['total'] or Decimal('0')
    total_safe_balance = safes.aggregate(total=Sum('current_balance'))['total'] or Decimal('0')
    cash_position = total_bank_balance + total_safe_balance

    bank_inflow_today = BankTransaction.objects.filter(
        bank__in=banks, date=today, transaction_type__in=['deposit', 'transfer_in', 'check_in']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    bank_outflow_today = BankTransaction.objects.filter(
        bank__in=banks, date=today, transaction_type__in=['withdrawal', 'transfer_out', 'check_out']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    safe_inflow_today = SafeTransaction.objects.filter(
        safe__in=safes, date=today, transaction_type__in=['deposit']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    safe_outflow_today = SafeTransaction.objects.filter(
        safe__in=safes, date=today, transaction_type__in=['withdrawal']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # ── أعمار الذمم (AR) ──
    ar_invoices = SalesInvoice.objects.filter(remaining_amount__gt=0, is_posted=True)
    total_ar = ar_invoices.aggregate(total=Sum('remaining_amount'))['total'] or Decimal('0')

    def _age_bucket(qs, days_col='due_date'):
        buckets = {
            'current': Decimal('0'),
            'b1_30': Decimal('0'),
            'b31_60': Decimal('0'),
            'b61_90': Decimal('0'),
            'b90_plus': Decimal('0'),
        }
        for inv in qs:
            due = inv.due_date
            if not due:
                bucket = 'current'
            else:
                diff = (today - due).days
                if diff <= 0:
                    bucket = 'current'
                elif diff <= 30:
                    bucket = 'b1_30'
                elif diff <= 60:
                    bucket = 'b31_60'
                elif diff <= 90:
                    bucket = 'b61_90'
                else:
                    bucket = 'b90_plus'
            buckets[bucket] += inv.remaining_amount
        return buckets

    ar_buckets = _age_bucket(ar_invoices)

    # ── أعمار الدائن (AP) ──
    ap_invoices = PurchaseInvoice.objects.filter(remaining_amount__gt=0, is_posted=True)
    total_ap = ap_invoices.aggregate(total=Sum('remaining_amount'))['total'] or Decimal('0')
    ap_buckets = _age_bucket(ap_invoices)

    # ── هامش الربح ──
    total_sales_month = SalesInvoice.objects.filter(date__gte=month_start, date__lte=today, is_posted=True).aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')
    total_profit_month = SalesInvoice.objects.filter(date__gte=month_start, date__lte=today, is_posted=True).aggregate(
        profit=Sum('gross_profit')
    )['profit'] or Decimal('0')
    profit_margin = float(total_profit_month / total_sales_month * 100) if total_sales_month else 0

    # ── أفضل العملاء والموردين ──
    top_customers = (
        SalesInvoice.objects.filter(is_posted=True)
        .values('customer__name')
        .annotate(total=Sum('total_amount'))
        .order_by('-total')[:5]
    )
    top_suppliers = (
        PurchaseInvoice.objects.filter(is_posted=True)
        .values('supplier__name')
        .annotate(total=Sum('total_amount'))
        .order_by('-total')[:5]
    )

    context = {
        'today': today,
        'cash_position': cash_position,
        'total_bank_balance': total_bank_balance,
        'total_safe_balance': total_safe_balance,
        'bank_inflow_today': bank_inflow_today,
        'bank_outflow_today': bank_outflow_today,
        'safe_inflow_today': safe_inflow_today,
        'safe_outflow_today': safe_outflow_today,
        'net_cash_flow_today': (bank_inflow_today + safe_inflow_today) - (bank_outflow_today + safe_outflow_today),
        'total_ar': total_ar,
        'ar_buckets': ar_buckets,
        'total_ap': total_ap,
        'ap_buckets': ap_buckets,
        'total_sales_month': total_sales_month,
        'total_profit_month': total_profit_month,
        'profit_margin': profit_margin,
        'top_customers': top_customers,
        'top_suppliers': top_suppliers,
    }
    return render(request, 'reports/financial_dashboard.html', context)


@screen_permission_required('reports.report', 'view')
@cache_page(300, key_prefix='wf_tracker')
@vary_on_cookie
def workflow_tracker(request):
    """شاشة تدفق العمل - تتبع مسار المستندات عبر الوحدات"""
    from concrete_production.models import CustomerRequest, ProductionBatch, ProductionOrder
    from contractors.models import Contract, ContractorPayment, InterimCertificate

    today = timezone.now().date()

    # المشتريات: فاتورة -> مدفوعة
    purchase_invoices = PurchaseInvoice.objects
    # المبيعات
    sales_invoices = SalesInvoice.objects
    # الإنتاج
    requests = CustomerRequest.objects.filter(created_at__date__gte=today.replace(month=1, day=1))
    orders = ProductionOrder.objects
    batches = ProductionBatch.objects
    # المقاولون
    contracts = Contract.objects
    certificates = InterimCertificate.objects
    payments = ContractorPayment.objects

    stages = [
        {
            'group': 'المشتريات',
            'color': '#0984e3',
            'steps': [
                {
                    'name': 'فواتير المشتريات',
                    'count': purchase_invoices.count(),
                    'url': '/purchases/invoices/',
                    'icon': 'fa-shopping-cart',
                },
                {'name': 'مرتجعات مشتريات', 'count': 0, 'url': '/purchase-returns/', 'icon': 'fa-undo'},
                {
                    'name': 'سندات دفع',
                    'count': 0,
                    'url': '/payment-receipts/?type=payment',
                    'icon': 'fa-file-invoice-dollar',
                },
            ],
        },
        {
            'group': 'المبيعات',
            'color': '#00b894',
            'steps': [
                {
                    'name': 'فواتير المبيعات',
                    'count': sales_invoices.count(),
                    'url': '/sales/invoices/',
                    'icon': 'fa-cash-register',
                },
                {'name': 'مرتجعات مبيعات', 'count': 0, 'url': '/sales-returns/', 'icon': 'fa-undo'},
                {
                    'name': 'سندات قبض',
                    'count': 0,
                    'url': '/payment-receipts/?type=receipt',
                    'icon': 'fa-file-invoice-dollar',
                },
            ],
        },
        {
            'group': 'إنتاج الخرسانة',
            'color': '#ff8c00',
            'steps': [
                {
                    'name': 'طلبات العملاء',
                    'count': requests.count(),
                    'url': '/concrete/requests/',
                    'icon': 'fa-file-alt',
                },
                {
                    'name': 'أوامر الإنتاج',
                    'count': orders.count(),
                    'url': '/concrete/orders/',
                    'icon': 'fa-clipboard-list',
                },
                {'name': 'الدفعات', 'count': batches.count(), 'url': '/concrete/batches/', 'icon': 'fa-industry'},
            ],
        },
        {
            'group': 'إدارة المشاريع',
            'color': '#6c5ce7',
            'steps': [
                {
                    'name': 'العقود',
                    'count': contracts.count(),
                    'url': '/contractors/contracts/',
                    'icon': 'fa-file-contract',
                },
                {
                    'name': 'المستخلصات',
                    'count': certificates.count(),
                    'url': '/contractors/certificates/',
                    'icon': 'fa-file-alt',
                },
                {
                    'name': 'المدفوعات',
                    'count': payments.count(),
                    'url': '/contractors/payments/',
                    'icon': 'fa-money-bill',
                },
            ],
        },
    ]

    context = {'today': today, 'stages': stages}
    return render(request, 'reports/workflow_tracker.html', context)


@screen_permission_required('reports.report', 'view')
def report_list(request):
    return render(request, 'reports/report_list.html')


@screen_permission_required('reports.report', 'view')
@cache_page(300)
@vary_on_cookie
def income_statement(request):
    date_from, date_to = _get_date_range(request)

    # Revenue
    sales_revenue = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True).aggregate(
        total=Sum('subtotal')
    )['total'] or Decimal('0')

    # Cost of Goods Sold - from sales invoice cost_of_goods, not purchases
    cogs = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True).aggregate(
        total=Sum('cost_of_goods')
    )['total'] or Decimal('0')

    gross_profit = sales_revenue - cogs

    # Operating Expenses - from posted journal lines within the period
    expense_accounts = Account.objects.filter(
        account_type__account_type='expense', code__startswith='5', is_active=True
    ).select_related('account_type')

    activity = _posted_lines_in_range(date_from, date_to)
    total_expenses = Decimal('0')
    expenses_detail = []
    for acc in expense_accounts:
        acc_act = activity.get(acc.pk, {'debit': Decimal('0'), 'credit': Decimal('0')})
        amount = acc_act['debit'] - acc_act['credit']
        amount = abs(amount)
        if amount > 0:
            expenses_detail.append({'name': acc.name, 'code': acc.code, 'amount': amount})
            total_expenses += amount

    operating_profit = gross_profit - total_expenses

    # Other Income/Expenses - from posted journal lines within the period
    other_income_accounts = Account.objects.filter(code__startswith='42', is_active=True).select_related('account_type')
    other_expense_accounts = Account.objects.filter(code__startswith='55', is_active=True).select_related(
        'account_type'
    )

    other_income = Decimal('0')
    for acc in other_income_accounts:
        acc_act = activity.get(acc.pk, {'debit': Decimal('0'), 'credit': Decimal('0')})
        other_income += acc_act['credit'] - acc_act['debit']

    other_expenses = Decimal('0')
    for acc in other_expense_accounts:
        acc_act = activity.get(acc.pk, {'debit': Decimal('0'), 'credit': Decimal('0')})
        other_expenses += acc_act['debit'] - acc_act['credit']

    net_profit = operating_profit + other_income - other_expenses

    # VAT
    vat_output = SalesInvoice.objects.filter(
        date__gte=date_from, date__lte=date_to, is_tax_invoice=True, is_posted=True
    ).aggregate(total=Sum('vat_amount'))['total'] or Decimal('0')

    vat_input = PurchaseInvoice.objects.filter(
        date__gte=date_from, date__lte=date_to, is_tax_invoice=True, is_posted=True
    ).aggregate(total=Sum('vat_amount'))['total'] or Decimal('0')

    vat_payable = vat_output - vat_input

    # Withholding Tax - from actual invoices
    withholding_tax = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True).aggregate(
        total=Sum('withholding_tax_amount')
    )['total'] or Decimal('0')

    # Net after taxes
    total_taxes = vat_payable + withholding_tax
    net_after_tax = net_profit - total_taxes

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'sales_revenue': sales_revenue,
        'cogs': cogs,
        'gross_profit': gross_profit,
        'expenses_detail': expenses_detail,
        'total_expenses': total_expenses,
        'operating_profit': operating_profit,
        'other_income': other_income,
        'other_expenses': other_expenses,
        'net_profit': net_profit,
        'vat_output': vat_output,
        'vat_input': vat_input,
        'vat_payable': vat_payable,
        'withholding_tax': withholding_tax,
        'total_taxes': total_taxes,
        'net_after_tax': net_after_tax,
    }
    return render(request, 'reports/income_statement.html', context)


@screen_permission_required('reports.report', 'view')
@cache_page(300)
@vary_on_cookie
def balance_sheet(request):
    date_from, date_to = _get_date_range(request)
    as_of = date_to

    # Assets
    current_assets = list(
        Account.objects.filter(
            account_type__account_type='asset', code__startswith='11', is_active=True
        ).select_related('account_type')
    )
    non_current_assets = list(
        Account.objects.filter(account_type__account_type='asset', code__startswith='1', is_active=True)
        .exclude(code__startswith='11')
        .select_related('account_type')
    )

    # Liabilities
    current_liabilities = list(
        Account.objects.filter(
            account_type__account_type='liability', code__startswith='21', is_active=True
        ).select_related('account_type')
    )
    non_current_liabilities = list(
        Account.objects.filter(account_type__account_type='liability', code__startswith='2', is_active=True)
        .exclude(code__startswith='21')
        .select_related('account_type')
    )

    # Equity
    equity_accounts = list(
        Account.objects.filter(account_type__account_type='equity', is_active=True).select_related('account_type')
    )

    # Compute balances as of date_to (opening + posted activity)
    all_bs_accounts = (
        current_assets + non_current_assets + current_liabilities + non_current_liabilities + equity_accounts
    )
    balances = _balances_as_of(all_bs_accounts, as_of)
    for acc in all_bs_accounts:
        acc.current_balance = balances[acc.pk]

    total_current_assets = sum((balances[a.pk] for a in current_assets), Decimal('0'))
    total_non_current_assets = sum((balances[a.pk] for a in non_current_assets), Decimal('0'))
    total_assets = total_current_assets + total_non_current_assets

    total_current_liabilities = sum((balances[a.pk] for a in current_liabilities), Decimal('0'))
    total_non_current_liabilities = sum((balances[a.pk] for a in non_current_liabilities), Decimal('0'))
    total_liabilities = total_current_liabilities + total_non_current_liabilities

    total_equity = sum((balances[a.pk] for a in equity_accounts), Decimal('0'))

    # Net Profit (period activity from posted lines)
    activity = _posted_lines_in_range(date_from, date_to)
    revenue_accounts = Account.objects.filter(account_type__account_type='revenue', is_active=True)
    expense_accounts = Account.objects.filter(account_type__account_type='expense', is_active=True)
    revenue = Decimal('0')
    for acc in revenue_accounts:
        acc_act = activity.get(acc.pk, {'debit': Decimal('0'), 'credit': Decimal('0')})
        revenue += acc_act['credit'] - acc_act['debit']
    expenses = Decimal('0')
    for acc in expense_accounts:
        acc_act = activity.get(acc.pk, {'debit': Decimal('0'), 'credit': Decimal('0')})
        expenses += acc_act['debit'] - acc_act['credit']
    net_profit = revenue - expenses

    context = {
        'current_assets': current_assets,
        'non_current_assets': non_current_assets,
        'total_current_assets': total_current_assets,
        'total_non_current_assets': total_non_current_assets,
        'total_assets': total_assets,
        'current_liabilities': current_liabilities,
        'non_current_liabilities': non_current_liabilities,
        'total_current_liabilities': total_current_liabilities,
        'total_non_current_liabilities': total_non_current_liabilities,
        'total_liabilities': total_liabilities,
        'equity_accounts': equity_accounts,
        'total_equity': total_equity,
        'net_profit': net_profit,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'reports/balance_sheet.html', context)


@screen_permission_required('reports.report', 'view')
@cache_page(300)
@vary_on_cookie
def trial_balance_report(request):
    date_from, date_to = _get_date_range(request)

    accounts = list(Account.objects.filter(is_active=True).select_related('account_type'))
    activity = _posted_lines_in_range(date_from, date_to)
    total_debit = Decimal('0')
    total_credit = Decimal('0')

    for acc in accounts:
        acc_act = activity.get(acc.pk, {'debit': Decimal('0'), 'credit': Decimal('0')})
        net = _period_net(acc_act, acc.account_type.account_type)
        # Override current_balance with the period net so the template displays correctly
        acc.current_balance = net
        debit, credit = _trial_balance_split(net, acc.account_type.account_type)
        total_debit += debit
        total_credit += credit

    return render(
        request,
        'reports/trial_balance_report.html',
        {
            'accounts': accounts,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'date_from': date_from,
            'date_to': date_to,
        },
    )


@screen_permission_required('reports.report', 'view')
@cache_page(300)
@vary_on_cookie
def general_ledger(request):
    from django.db.models import F

    from common.utils import parse_date_range

    account_id = request.GET.get('account')
    date_from, date_to = parse_date_range(request)

    lines = (
        JournalEntryLine.objects.filter(journal_entry__is_posted=True)
        .select_related('journal_entry', 'account', 'account__account_type')
        .order_by('journal_entry__date', 'journal_entry__entry_number', 'id')
    )
    if date_from:
        lines = lines.filter(journal_entry__date__gte=date_from)
    if date_to:
        lines = lines.filter(journal_entry__date__lte=date_to)
    if account_id:
        lines = lines.filter(account_id=account_id)

    # Opening balances per account (up to date_from)
    accounts_qs = Account.objects.filter(is_active=True).select_related('account_type')
    if account_id:
        accounts_qs = accounts_qs.filter(pk=account_id)
    running = {}
    for acc in accounts_qs:
        ob = acc.opening_balance
        if date_from:
            pre = JournalEntryLine.objects.filter(
                account=acc, journal_entry__is_posted=True, journal_entry__date__lt=date_from
            ).aggregate(s=Sum(F('debit') - F('credit')))['s'] or Decimal('0')
            ob += pre
        running[acc.pk] = ob

    total_debit = Decimal('0')
    total_credit = Decimal('0')
    ledger = []
    for line in lines:
        total_debit += line.debit
        total_credit += line.credit
        running[line.account_id] = running.get(line.account_id, Decimal('0')) + line.debit - line.credit
        ledger.append(
            {
                'date': line.journal_entry.date,
                'entry_number': line.journal_entry.entry_number,
                'account_code': line.account.code,
                'account_name': line.account.name,
                'description': line.description or line.journal_entry.description,
                'debit': line.debit,
                'credit': line.credit,
                'balance': running[line.account_id],
            }
        )

    all_accounts = Account.objects.filter(is_active=True).select_related('account_type').order_by('code')

    context = {
        'ledger': ledger,
        'accounts': all_accounts,
        'selected_account': account_id,
        'date_from': date_from,
        'date_to': date_to,
        'total_debit': total_debit,
        'total_credit': total_credit,
    }
    return render(request, 'reports/general_ledger.html', context)


@screen_permission_required('reports.report', 'view')
def vat_return(request):
    date_from, date_to = _get_date_range(request)

    # Sales with VAT
    taxable_sales = SalesInvoice.objects.filter(
        date__gte=date_from, date__lte=date_to, is_tax_invoice=True, is_posted=True
    )
    total_taxable_sales = taxable_sales.aggregate(total=Sum('subtotal'))['total'] or Decimal('0')
    total_vat_output = taxable_sales.aggregate(total=Sum('vat_amount'))['total'] or Decimal('0')

    # Purchases with VAT
    taxable_purchases = PurchaseInvoice.objects.filter(
        date__gte=date_from, date__lte=date_to, is_tax_invoice=True, is_posted=True
    )
    total_taxable_purchases = taxable_purchases.aggregate(total=Sum('subtotal'))['total'] or Decimal('0')
    total_vat_input = taxable_purchases.aggregate(total=Sum('vat_amount'))['total'] or Decimal('0')

    # VAT Settlement
    vat_payable = total_vat_output - total_vat_input

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'total_taxable_sales': total_taxable_sales,
        'total_vat_output': total_vat_output,
        'total_taxable_purchases': total_taxable_purchases,
        'total_vat_input': total_vat_input,
        'vat_payable': vat_payable,
    }
    return render(request, 'reports/vat_return.html', context)


@screen_permission_required('reports.report', 'view')
def withholding_tax_report(request):
    date_from, date_to = _get_date_range(request)

    purchases = PurchaseInvoice.objects.filter(
        date__gte=date_from, date__lte=date_to, is_posted=True, withholding_tax_amount__gt=0
    ).select_related('supplier')

    withholding_items = []
    total_withholding = Decimal('0')
    total_subtotal = Decimal('0')
    for inv in purchases:
        if inv.withholding_tax_amount > 0:
            rate = inv.withholding_tax_type
            withholding_items.append(
                {'invoice': inv, 'subtotal': inv.subtotal, 'rate': rate, 'amount': inv.withholding_tax_amount}
            )
            total_withholding += inv.withholding_tax_amount
            total_subtotal += inv.subtotal

    # Summary by rate
    rate_summary = {}
    for item in withholding_items:
        r = item['rate']
        if r not in rate_summary:
            rate_summary[r] = {'count': 0, 'subtotal': Decimal('0'), 'amount': Decimal('0')}
        rate_summary[r]['count'] += 1
        rate_summary[r]['subtotal'] += item['subtotal']
        rate_summary[r]['amount'] += item['amount']

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'withholding_items': withholding_items,
        'total_withholding': total_withholding,
        'total_subtotal': total_subtotal,
        'rate_summary': rate_summary,
    }
    return render(request, 'reports/withholding_tax_report.html', context)


@screen_permission_required('reports.report', 'view')
def supplier_report(request):
    suppliers = Supplier.objects.filter(is_active=True).annotate(
        purchase_count=Count('purchaseinvoice'),
        total_purchases=Sum('purchaseinvoice__total_amount'),
        total_paid=Sum('purchaseinvoice__paid_amount'),
    )
    return render(request, 'reports/supplier_report.html', {'suppliers': suppliers})


@screen_permission_required('reports.report', 'view')
def supplier_detail_report(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    invoices = PurchaseInvoice.objects.filter(supplier=supplier).order_by('-date')
    total_purchases = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    total_paid = invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    total_remaining = total_purchases - total_paid

    return render(
        request,
        'reports/supplier_detail_report.html',
        {
            'supplier': supplier,
            'invoices': invoices,
            'total_purchases': total_purchases,
            'total_paid': total_paid,
            'total_remaining': total_remaining,
        },
    )


@screen_permission_required('reports.report', 'view')
def customer_report(request):
    customers = Customer.objects.filter(is_active=True).annotate(
        sales_count=Count('salesinvoice'),
        total_sales=Sum('salesinvoice__total_amount'),
        total_collected=Sum('salesinvoice__paid_amount'),
    )
    return render(request, 'reports/customer_report.html', {'customers': customers})


@screen_permission_required('reports.report', 'view')
def customer_detail_report(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    invoices = SalesInvoice.objects.filter(customer=customer).order_by('-date')
    total_sales = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    total_collected = invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    total_remaining = total_sales - total_collected

    return render(
        request,
        'reports/customer_detail_report.html',
        {
            'customer': customer,
            'invoices': invoices,
            'total_sales': total_sales,
            'total_collected': total_collected,
            'total_remaining': total_remaining,
        },
    )


@screen_permission_required('reports.report', 'view')
@cache_page(300)
@vary_on_cookie
def profit_margin_report(request):
    date_from, date_to = _get_date_range(request)

    product_data_raw = (
        SalesInvoiceLine.objects.filter(
            invoice__date__gte=date_from, invoice__date__lte=date_to, invoice__is_posted=True
        )
        .values('product__id', 'product__code', 'product__name')
        .annotate(total_qty=Sum('quantity'), total_sales=Sum('total_price'), total_cost=Sum('cost_total'))
        .order_by('-total_sales')
    )

    product_data = []
    for row in product_data_raw:
        total_sales = row['total_sales'] or Decimal('0')
        total_cost = row['total_cost'] or Decimal('0')
        total_profit = total_sales - total_cost
        margin = (total_profit / total_sales * 100) if total_sales > 0 else Decimal('0')
        product_data.append(
            {
                'product_name': row['product__name'],
                'product_code': row['product__code'],
                'total_qty': row['total_qty'] or Decimal('0'),
                'total_sales': total_sales,
                'total_cost': total_cost,
                'total_profit': total_profit,
                'margin': margin,
            }
        )

    total_sales_all = sum(d['total_sales'] for d in product_data)
    total_cost_all = sum(d['total_cost'] for d in product_data)
    total_profit_all = total_sales_all - total_cost_all
    overall_margin = (total_profit_all / total_sales_all * 100) if total_sales_all > 0 else Decimal('0')

    return render(
        request,
        'reports/profit_margin_report.html',
        {
            'date_from': date_from,
            'date_to': date_to,
            'product_data': product_data,
            'total_sales_all': total_sales_all,
            'total_cost_all': total_cost_all,
            'total_profit_all': total_profit_all,
            'overall_margin': overall_margin,
        },
    )


@screen_permission_required('reports.report', 'view')
def asset_schedule(request):
    assets = Asset.objects.filter(is_active=True).select_related('category')
    depreciation_entries = DepreciationEntry.objects.select_related('asset').all()[:50]

    agg = assets.aggregate(
        total_cost=Sum('purchase_price'),
        total_depreciation=Sum('accumulated_depreciation'),
        total_net=Sum('net_book_value'),
    )

    return render(
        request,
        'reports/asset_schedule.html',
        {
            'assets': assets,
            'depreciation_entries': depreciation_entries,
            'total_cost': agg['total_cost'] or Decimal('0'),
            'total_depreciation': agg['total_depreciation'] or Decimal('0'),
            'total_net': agg['total_net'] or Decimal('0'),
        },
    )


@screen_permission_required('reports.report', 'view')
def payroll_report(request):
    year = request.GET.get('year', timezone.now().year)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = timezone.now().year

    salaries = Salary.objects.filter(year=year).select_related('employee').order_by('month')

    total_salaries = salaries.aggregate(
        total_basic=Sum('basic_salary'),
        total_allowances=Sum('allowances'),
        total_overtime=Sum('overtime'),
        total_bonus=Sum('bonus'),
        total_deductions=Sum('deductions'),
        total_social_insurance=Sum('social_insurance'),
        total_income_tax=Sum('income_tax'),
        total_net=Sum('net_salary'),
    )

    return render(
        request,
        'reports/payroll_report.html',
        {
            'year': year,
            'years': range(timezone.now().year - 5, timezone.now().year + 1),
            'salaries': salaries,
            'total_salaries': total_salaries,
        },
    )


@screen_permission_required('reports.report', 'export')
def export_report(request, report_type):
    fmt = request.GET.get('format', 'excel')
    today = timezone.now().date()

    raw_from = request.GET.get('date_from')
    raw_to = request.GET.get('date_to')
    date_from = _safe_parse_date(raw_from, 'date_from') if raw_from else None
    date_to = _safe_parse_date(raw_to, 'date_to') if raw_to else None

    if date_from is None:
        date_from = today.replace(day=1)
    if date_to is None:
        date_to = today

    date_from, date_to = _validate_date_range(request, date_from, date_to)

    exporters = {
        'daily-sales': _export_daily_sales,
        'daily-purchases': _export_daily_purchases,
        'ar-aging': _export_ar_aging,
        'ap-aging': _export_ap_aging,
        'income-statement': _export_income_statement,
        'balance-sheet': _export_balance_sheet,
        'vat-return': _export_vat_return,
        'payroll': _export_payroll,
        'inventory': _export_inventory,
        'stock-valuation': _export_stock_valuation,
        'profit-margin': _export_profit_margin,
        'withholding-tax': _export_withholding_tax,
        'supplier-report': _export_supplier_report,
        'customer-report': _export_customer_report,
        'customer-statement': _export_customer_statement,
        'supplier-statement': _export_supplier_statement,
        'trial-balance': _export_trial_balance,
        'general-ledger': _export_general_ledger,
        'asset-schedule': _export_asset_schedule,
        'cash-flow': _export_cash_flow,
        'budget-vs-actual': _export_budget_vs_actual,
        'bank-reconciliation': _export_bank_reconciliation,
        'tax-summary': _export_tax_summary,
        'payroll-detail': _export_payroll_detail,
    }

    exporter = exporters.get(report_type)
    if exporter:
        return exporter(request, date_from, date_to, fmt)
    return HttpResponse('نوع التقرير غير معروف', status=404)


def _export_simple_xlsx(headers, rows, filename):
    columns = [{'header': h, 'width': 18} for h in headers]

    class RowObj:
        def __init__(self, vals, hdrs):
            self._vals = vals
            self._hdrs = hdrs

        def __getattr__(self, name):
            try:
                return self._vals[self._hdrs.index(name)]
            except (ValueError, IndexError):
                return ''

    qs = [RowObj(row, headers) for row in rows]
    col_defs = [{'field': lambda obj, h=h: getattr(obj, h, ''), 'header': h, 'width': 18} for h in headers]
    return export_to_excel(qs, col_defs, filename)


def _export_daily_sales(request, date_from, date_to, fmt):
    invoices = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True).select_related(
        'customer'
    )
    headers = ['التاريخ', 'رقم الفاتورة', 'العميل', 'المبلغ', 'الضريبة', 'الإجمالي', 'المدفوع', 'المتبقي']
    rows, totals = [], [Decimal('0')] * 4
    for inv in invoices:
        rows.append(
            [
                inv.date.strftime('%d/%m/%Y'),
                inv.invoice_number,
                inv.customer.name,
                str(inv.subtotal),
                str(inv.vat_amount),
                str(inv.total_amount),
                str(inv.paid_amount),
                str(inv.remaining_amount),
            ]
        )
        totals[0] += inv.total_amount
        totals[1] += inv.vat_amount
        totals[2] += inv.paid_amount
        totals[3] += inv.remaining_amount
    summary = {
        'الإجمالي': str(totals[0]),
        'الضريبة': str(totals[1]),
        'المدفوع': str(totals[2]),
        'المتبقي': str(totals[3]),
    }
    if fmt == 'pdf':
        return export_to_pdf(f'يومية المبيعات من {date_from} إلى {date_to}', headers, rows, 'daily_sales', summary)
    return _export_simple_xlsx(headers, rows, 'daily_sales')


def _export_daily_purchases(request, date_from, date_to, fmt):
    invoices = PurchaseInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True).select_related(
        'supplier'
    )
    headers = ['التاريخ', 'رقم الفاتورة', 'المورد', 'المبلغ', 'الضريبة', 'الإجمالي', 'المدفوع', 'المتبقي']
    rows = []
    for inv in invoices:
        rows.append(
            [
                inv.date.strftime('%d/%m/%Y'),
                inv.invoice_number,
                inv.supplier.name,
                str(inv.subtotal),
                str(inv.vat_amount),
                str(inv.total_amount),
                str(inv.paid_amount),
                str(inv.remaining_amount),
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'يومية المشتريات من {date_from} إلى {date_to}', headers, rows, 'daily_purchases')
    return _export_simple_xlsx(headers, rows, 'daily_purchases')


def _export_ar_aging(request, date_from, date_to, fmt):
    invoices = SalesInvoice.objects.filter(remaining_amount__gt=0, is_posted=True).select_related('customer')
    headers = ['العميل', 'رقم الفاتورة', 'الإجمالي', 'المتبقي', 'تاريخ الاستحقاق', 'أيام التأخير']
    rows = []
    for inv in invoices:
        days = (date_to - inv.due_date).days if inv.due_date else 0
        rows.append(
            [
                inv.customer.name,
                inv.invoice_number,
                str(inv.total_amount),
                str(inv.remaining_amount),
                inv.due_date.strftime('%d/%m/%Y') if inv.due_date else '-',
                str(max(0, days)),
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'أعمار الذمم المدينة إلى {date_to}', headers, rows, 'ar_aging')
    return _export_simple_xlsx(headers, rows, 'ar_aging')


def _export_ap_aging(request, date_from, date_to, fmt):
    invoices = PurchaseInvoice.objects.filter(remaining_amount__gt=0, is_posted=True).select_related('supplier')
    headers = ['المورد', 'رقم الفاتورة', 'الإجمالي', 'المتبقي', 'تاريخ الاستحقاق', 'أيام التأخير']
    rows = []
    for inv in invoices:
        days = (date_to - inv.due_date).days if inv.due_date else 0
        rows.append(
            [
                inv.supplier.name,
                inv.invoice_number,
                str(inv.total_amount),
                str(inv.remaining_amount),
                inv.due_date.strftime('%d/%m/%Y') if inv.due_date else '-',
                str(max(0, days)),
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'أعمار الذمم الدائنة إلى {date_to}', headers, rows, 'ap_aging')
    return _export_simple_xlsx(headers, rows, 'ap_aging')


def _export_income_statement(request, date_from, date_to, fmt):
    rev = Account.objects.filter(account_type__name='إيرادات', is_active=True)
    exp = Account.objects.filter(account_type__name='مصروفات', is_active=True)
    headers = ['الحساب', 'الكود', 'الرصيد']
    rows = [[a.name, a.code, str(a.current_balance or 0)] for a in list(rev) + list(exp)]
    if fmt == 'pdf':
        return export_to_pdf(f'قائمة الدخل من {date_from} إلى {date_to}', headers, rows, 'income_statement')
    return _export_simple_xlsx(headers, rows, 'income_statement')


def _export_balance_sheet(request, date_from, date_to, fmt):
    headers = ['الحساب', 'الكود', 'الرصيد', 'النوع']
    rows = []
    for a in Account.objects.filter(account_type__name='أصول', is_active=True):
        rows.append([a.name, a.code, str(a.current_balance or 0), 'أصول'])
    for a in Account.objects.filter(account_type__name='خصوم', is_active=True):
        rows.append([a.name, a.code, str(a.current_balance or 0), 'خصوم'])
    for a in Account.objects.filter(account_type__name='حقوق الملكية', is_active=True):
        rows.append([a.name, a.code, str(a.current_balance or 0), 'حقوق ملكية'])
    if fmt == 'pdf':
        return export_to_pdf(f'الميزانية العمومية إلى {date_to}', headers, rows, 'balance_sheet')
    return _export_simple_xlsx(headers, rows, 'balance_sheet')


def _export_vat_return(request, date_from, date_to, fmt):
    sales = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_tax_invoice=True, is_posted=True)
    purchases = PurchaseInvoice.objects.filter(
        date__gte=date_from, date__lte=date_to, is_tax_invoice=True, is_posted=True
    )
    headers = ['البيان', 'المبلغ', 'الضريبة']
    vo = sales.aggregate(s=Sum('subtotal'), v=Sum('vat_amount'))
    vi = purchases.aggregate(s=Sum('subtotal'), v=Sum('vat_amount'))
    rows = [
        ['مبيعات خاضعة للضريبة', str(vo['s'] or 0), str(vo['v'] or 0)],
        ['مشتريات خاضعة للضريبة', str(vi['s'] or 0), str(vi['v'] or 0)],
        ['الضريبة المستحقة', '', str((vo['v'] or 0) - (vi['v'] or 0))],
    ]
    if fmt == 'pdf':
        return export_to_pdf(f'إقرار VAT من {date_from} إلى {date_to}', headers, rows, 'vat_return')
    return _export_simple_xlsx(headers, rows, 'vat_return')


def _export_payroll(request, date_from, date_to, fmt):
    salaries = Salary.objects.filter(payment_date__gte=date_from, payment_date__lte=date_to).select_related('employee')
    headers = [
        'الموظف',
        'الراتب الأساسي',
        'العلاوات',
        'العمل الإضافي',
        'المكافآت',
        'الخصومات',
        'التأمين',
        'الضريبة',
        'صافي الراتب',
    ]
    rows = []
    for s in salaries:
        rows.append(
            [
                f'{s.employee.first_name} {s.employee.last_name}',
                str(s.basic_salary),
                str(s.allowances),
                str(s.overtime),
                str(s.bonus),
                str(s.deductions),
                str(s.social_insurance),
                str(s.income_tax),
                str(s.net_salary),
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'تقرير الرواتب من {date_from} إلى {date_to}', headers, rows, 'payroll')
    return _export_simple_xlsx(headers, rows, 'payroll')


def _export_inventory(request, date_from, date_to, fmt):
    items = WarehouseProduct.objects.select_related('warehouse', 'product')
    headers = ['المخزون', 'المنتج', 'الكمية', 'الحد الأدنى', 'الحد الأقصى', 'الحالة']
    rows = []
    for item in items:
        status = (
            'منخفض'
            if item.quantity <= item.minimum_quantity
            else ('زائد' if item.maximum_quantity and item.quantity > item.maximum_quantity else 'طبيعي')
        )
        rows.append(
            [
                item.warehouse.name,
                item.product.name,
                str(item.quantity),
                str(item.minimum_quantity),
                str(item.maximum_quantity or '-'),
                status,
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'تقرير المخزون - {date_from}', headers, rows, 'inventory')
    return _export_simple_xlsx(headers, rows, 'inventory')


def _export_stock_valuation(request, date_from, date_to, fmt):
    layers = (
        InventoryCostLayer.objects.filter(is_active=True, quantity_remaining__gt=0)
        .select_related('product', 'warehouse')
        .order_by('product__code')
    )
    headers = ['المخزن', 'المنتج', 'الكمية المتبقية', 'تكلفة الوحدة', 'القيمة', 'التاريخ', 'المرجع']
    rows = []
    for layer in layers:
        rows.append(
            [
                layer.warehouse.name,
                layer.product.name,
                str(layer.quantity_remaining),
                str(layer.unit_cost),
                str(layer.total_cost),
                layer.date.strftime('%d/%m/%Y'),
                layer.reference_number or '-',
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf('تقييم المخزون FIFO', headers, rows, 'stock_valuation')
    return _export_simple_xlsx(headers, rows, 'stock_valuation')


def _export_profit_margin(request, date_from, date_to, fmt):
    invoices = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True).select_related(
        'customer'
    )
    headers = ['رقم الفاتورة', 'العميل', 'المبيعات', 'تكلفة البضاعة', 'الربح', 'نسبة الربح %']
    rows = []
    for inv in invoices:
        margin = round((inv.gross_profit / inv.total_amount * 100), 1) if inv.total_amount else 0
        rows.append(
            [
                inv.invoice_number,
                inv.customer.name,
                str(inv.total_amount),
                str(inv.cost_of_goods),
                str(inv.gross_profit),
                f'{margin}%',
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'نسب الربح من {date_from} إلى {date_to}', headers, rows, 'profit_margin')
    return _export_simple_xlsx(headers, rows, 'profit_margin')


def _export_withholding_tax(request, date_from, date_to, fmt):
    from purchases.models import PurchaseInvoice as PI
    from sales.models import SalesInvoice as SI

    sales = SI.objects.filter(
        date__gte=date_from, date__lte=date_to, is_posted=True, withholding_tax_type__gt=0
    ).select_related('customer')
    purchases = PI.objects.filter(
        date__gte=date_from, date__lte=date_to, is_posted=True, withholding_tax_type__gt=0
    ).select_related('supplier')
    headers = ['النوع', 'الطرف', 'رقم الفاتورة', 'المبلغ', 'نسبة الاقتطاع', 'مبلغ الاقتطاع']
    rows = []
    for inv in sales:
        rows.append(
            [
                'مبيعات',
                inv.customer.name,
                inv.invoice_number,
                str(inv.total_amount),
                f'{inv.get_withholding_tax_type_display()}',
                str(inv.withholding_tax_amount),
            ]
        )
    for inv in purchases:
        rows.append(
            [
                'مشتريات',
                inv.supplier.name,
                inv.invoice_number,
                str(inv.total_amount),
                f'{inv.get_withholding_tax_type_display()}',
                str(inv.withholding_tax_amount),
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'ضريبة الخصم والتحصيل من {date_from} إلى {date_to}', headers, rows, 'withholding_tax')
    return _export_simple_xlsx(headers, rows, 'withholding_tax')


def _export_supplier_report(request, date_from, date_to, fmt):
    supplier_agg = Supplier.objects.filter(
        purchaseinvoice__is_posted=True, purchaseinvoice__date__gte=date_from, purchaseinvoice__date__lte=date_to
    ).annotate(
        t=Sum('purchaseinvoice__total_amount'),
        p=Sum('purchaseinvoice__paid_amount'),
        r=Sum('purchaseinvoice__remaining_amount'),
        c=Count('purchaseinvoice'),
    )
    headers = ['المورد', 'إجمالي المشتريات', 'المدفوع', 'المتبقي', 'عدد الفواتير']
    rows = []
    for sup in supplier_agg:
        if sup.t:
            rows.append([sup.name, str(sup.t or 0), str(sup.p or 0), str(sup.r or 0), str(sup.c or 0)])
    if fmt == 'pdf':
        return export_to_pdf(f'تقرير الموردين من {date_from} إلى {date_to}', headers, rows, 'supplier_report')
    return _export_simple_xlsx(headers, rows, 'supplier_report')


def _export_customer_report(request, date_from, date_to, fmt):
    customer_agg = Customer.objects.filter(
        salesinvoice__is_posted=True, salesinvoice__date__gte=date_from, salesinvoice__date__lte=date_to
    ).annotate(
        t=Sum('salesinvoice__total_amount'),
        p=Sum('salesinvoice__paid_amount'),
        r=Sum('salesinvoice__remaining_amount'),
        c=Count('salesinvoice'),
    )
    headers = ['العميل', 'إجمالي المبيعات', 'المدفوع', 'المتبقي', 'عدد الفواتير']
    rows = []
    for cust in customer_agg:
        if cust.t:
            rows.append([cust.name, str(cust.t or 0), str(cust.p or 0), str(cust.r or 0), str(cust.c or 0)])
    if fmt == 'pdf':
        return export_to_pdf(f'تقرير العملاء من {date_from} إلى {date_to}', headers, rows, 'customer_report')
    return _export_simple_xlsx(headers, rows, 'customer_report')


def _export_customer_statement(request, date_from, date_to, fmt):
    customers = (
        Customer.objects.filter(salesinvoice__is_posted=True)
        .annotate(
            open_bal=Sum('salesinvoice__total_amount', filter=Q(salesinvoice__date__lt=date_from))
            - Sum('salesinvoice__paid_amount', filter=Q(salesinvoice__date__lt=date_from)),
            sales_total=Sum(
                'salesinvoice__total_amount',
                filter=Q(salesinvoice__date__gte=date_from, salesinvoice__date__lte=date_to),
            ),
            paid_total=Sum(
                'salesinvoice__paid_amount',
                filter=Q(salesinvoice__date__gte=date_from, salesinvoice__date__lte=date_to),
            ),
        )
        .distinct()
    )
    headers = ['العميل', 'الرصيد الافتتاحي', 'المبيعات', 'المدفوع', 'الرصيد الختامي']
    rows = []
    for cust in customers:
        ob = cust.open_bal or 0
        st = cust.sales_total or 0
        pt = cust.paid_total or 0
        cb = ob + st - pt
        if ob or st:
            rows.append([cust.name, str(ob), str(st), str(pt), str(cb)])
    if fmt == 'pdf':
        return export_to_pdf(f'كشف حساب العملاء من {date_from} إلى {date_to}', headers, rows, 'customer_statement')
    return _export_simple_xlsx(headers, rows, 'customer_statement')


def _export_supplier_statement(request, date_from, date_to, fmt):
    suppliers = (
        Supplier.objects.filter(purchaseinvoice__is_posted=True)
        .annotate(
            open_bal=Sum('purchaseinvoice__total_amount', filter=Q(purchaseinvoice__date__lt=date_from))
            - Sum('purchaseinvoice__paid_amount', filter=Q(purchaseinvoice__date__lt=date_from)),
            purchase_total=Sum(
                'purchaseinvoice__total_amount',
                filter=Q(purchaseinvoice__date__gte=date_from, purchaseinvoice__date__lte=date_to),
            ),
            paid_total=Sum(
                'purchaseinvoice__paid_amount',
                filter=Q(purchaseinvoice__date__gte=date_from, purchaseinvoice__date__lte=date_to),
            ),
        )
        .distinct()
    )
    headers = ['المورد', 'الرصيد الافتتاحي', 'المشتريات', 'المدفوع', 'الرصيد الختامي']
    rows = []
    for sup in suppliers:
        ob = sup.open_bal or 0
        pt = sup.purchase_total or 0
        pd = sup.paid_total or 0
        cb = ob + pt - pd
        if ob or pt:
            rows.append([sup.name, str(ob), str(pt), str(pd), str(cb)])
    if fmt == 'pdf':
        return export_to_pdf(f'كشف حساب الموردين من {date_from} إلى {date_to}', headers, rows, 'supplier_statement')
    return _export_simple_xlsx(headers, rows, 'supplier_statement')


def _export_trial_balance(request, date_from, date_to, fmt):
    from accounts.models import Account

    accounts = Account.objects.filter(is_active=True).select_related('account_type')
    headers = ['الكود', 'الحساب', 'النوع', 'الرصيد']
    rows = []
    for a in accounts:
        rows.append([a.code, a.name, str(a.account_type.name if a.account_type else ''), str(a.current_balance or 0)])
    if fmt == 'pdf':
        return export_to_pdf(f'ميزان المراجعة إلى {date_to}', headers, rows, 'trial_balance')
    return _export_simple_xlsx(headers, rows, 'trial_balance')


def _export_general_ledger(request, date_from, date_to, fmt):
    account_id = request.GET.get('account')
    lines = (
        JournalEntryLine.objects.filter(journal_entry__is_posted=True)
        .select_related('journal_entry', 'account')
        .order_by('journal_entry__date', 'journal_entry__entry_number', 'id')
    )
    if date_from:
        lines = lines.filter(journal_entry__date__gte=date_from)
    if date_to:
        lines = lines.filter(journal_entry__date__lte=date_to)
    if account_id:
        lines = lines.filter(account_id=account_id)

    headers = ['التاريخ', 'رقم القيد', 'الحساب', 'البيان', 'مدين', 'دائن']
    rows = []
    for line in lines:
        rows.append(
            [
                line.journal_entry.date.strftime('%d/%m/%Y'),
                line.journal_entry.entry_number,
                f'{line.account.code} - {line.account.name}',
                line.description or line.journal_entry.description or '',
                str(line.debit),
                str(line.credit),
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'دفتر الأستاذ العام من {date_from} إلى {date_to}', headers, rows, 'general_ledger')
    return _export_simple_xlsx(headers, rows, 'general_ledger')


def _export_asset_schedule(request, date_from, date_to, fmt):
    assets = Asset.objects.annotate(dep_total=Sum('depreciationentry__amount')).all()
    headers = ['الأصل', 'التكلفة', 'الإهلاك المتراكم', 'الصافي', 'نسبة الإهلاك %']
    rows = []
    for a in assets:
        dep = a.dep_total or 0
        nbv = a.purchase_price - dep
        pct = round(dep / a.purchase_price * 100, 1) if a.purchase_price else 0
        rows.append([a.name, str(a.purchase_price), str(dep), str(nbv), f'{pct}%'])
    if fmt == 'pdf':
        return export_to_pdf(f'جدول الأصول والإهلاك - {date_to}', headers, rows, 'asset_schedule')
    return _export_simple_xlsx(headers, rows, 'asset_schedule')


def _export_cash_flow(request, date_from, date_to, fmt):
    from payment_receipts.models import PaymentReceipt

    sales_invoices = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True)
    purchase_invoices = PurchaseInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True)
    receipts = PaymentReceipt.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True)
    collection_cash = receipts.filter(receipt_type='receipt', payment_method='cash').aggregate(t=Sum('amount'))[
        't'
    ] or Decimal('0')
    payment_cash = receipts.filter(receipt_type='payment', payment_method='cash').aggregate(t=Sum('amount'))[
        't'
    ] or Decimal('0')
    collection_bank = receipts.filter(receipt_type='receipt', payment_method='bank_transfer').aggregate(
        t=Sum('amount')
    )['t'] or Decimal('0')
    payment_bank = receipts.filter(receipt_type='payment', payment_method='bank_transfer').aggregate(t=Sum('amount'))[
        't'
    ] or Decimal('0')
    cash_in = sales_invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    cash_out = purchase_invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    bank_deposits = BankTransaction.objects.filter(
        date__gte=date_from, date__lte=date_to, transaction_type='deposit'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    bank_withdrawals = BankTransaction.objects.filter(
        date__gte=date_from, date__lte=date_to, transaction_type='withdrawal'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    headers = ['البيان', 'المبلغ']
    rows = [
        ['تحصيل نقداً من العملاء', str(collection_cash)],
        ['تحويلات بنكية واردة', str(collection_bank)],
        ['إيداعات في البنوك', str(bank_deposits)],
        ['مدفوعات فواتير مبيعات', str(cash_in)],
        ['التدفقات الواردة الإجمالي', str(collection_cash + collection_bank + bank_deposits + cash_in)],
        ['', ''],
        ['مدفوعات نقدية للموردين', str(payment_cash)],
        ['تحويلات بنكية صادرة', str(payment_bank)],
        ['سحوبات من البنوك', str(bank_withdrawals)],
        ['مدفوعات فواتير مشتريات', str(cash_out)],
        ['التدفقات الصادرة الإجمالي', str(payment_cash + payment_bank + bank_withdrawals + cash_out)],
        ['', ''],
        [
            'صافي التدفق النقدي',
            str(
                (collection_cash + collection_bank + bank_deposits + cash_in)
                - (payment_cash + payment_bank + bank_withdrawals + cash_out)
            ),
        ],
    ]
    if fmt == 'pdf':
        return export_to_pdf(f'التدفق النقدي من {date_from} إلى {date_to}', headers, rows, 'cash_flow')
    return _export_simple_xlsx(headers, rows, 'cash_flow')


def _export_budget_vs_actual(request, date_from, date_to, fmt):
    year = request.GET.get('year', timezone.now().year)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = timezone.now().year
    month = request.GET.get('month', '')
    try:
        month = int(month) if month else None
    except (ValueError, TypeError):
        month = None
    cost_center_id = request.GET.get('cost_center') or None

    budgets = Budget.objects.filter(year=year)
    if month:
        budgets = budgets.filter(month=month)
    if cost_center_id:
        budgets = budgets.filter(cost_center_id=cost_center_id)
    budgets = budgets.select_related('account', 'account__account_type')

    if month:
        dfrom = timezone.now().replace(year=year, month=month, day=1).date()
        dto = (dfrom.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    else:
        dfrom = timezone.now().replace(year=year, month=1, day=1).date()
        dto = dfrom.replace(month=12, day=31)

    activity = _posted_lines_in_range(dfrom, dto)
    headers = ['الكود', 'الحساب', 'المخطط', 'الفعلي', 'الفرق', 'نسبة الفرق %']
    rows = []
    for b in budgets:
        acc_type = b.account.account_type.account_type if b.account.account_type else 'expense'
        acc_act = activity.get(b.account_id, {'debit': Decimal('0'), 'credit': Decimal('0')})
        actual = _period_net(acc_act, acc_type)
        variance = actual - b.budgeted_amount
        pct = round((variance / b.budgeted_amount * 100), 1) if b.budgeted_amount else 0
        rows.append([b.account.code, b.account.name, str(b.budgeted_amount), str(actual), str(variance), f'{pct}%'])
    if fmt == 'pdf':
        return export_to_pdf(f'الموازنة مقابل الفعلي {year}', headers, rows, 'budget_vs_actual')
    return _export_simple_xlsx(headers, rows, 'budget_vs_actual')


def _export_bank_reconciliation(request, date_from, date_to, fmt):
    banks = Bank.objects.filter(is_active=True).select_related('account', 'account__account_type')
    book_accounts = [b.account for b in banks if b.account]
    balances = _balances_as_of(book_accounts, date_to) if book_accounts else {}
    cheques = Cheque.objects.filter(status__in=['pending', 'deposited'], due_date__lte=date_to)
    headers = ['البنك', 'رصيد الدفتر', 'رصيد البيان', 'الشيكات غير المحصلة', 'الفرق']
    rows = []
    for bank in banks:
        book_balance = balances.get(bank.account_id, Decimal('0')) if bank.account else Decimal('0')
        outstanding = cheques.filter(bank_account=bank.account).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        diff = book_balance - outstanding
        rows.append([bank.name, str(book_balance), '-', str(outstanding), str(diff)])
    if fmt == 'pdf':
        return export_to_pdf(f'كشف التسوية البنكية إلى {date_to}', headers, rows, 'bank_reconciliation')
    return _export_simple_xlsx(headers, rows, 'bank_reconciliation')


def _export_tax_summary(request, date_from, date_to, fmt):
    invoices = TaxInvoice.objects.all()
    if date_from:
        invoices = invoices.filter(created_at__date__gte=date_from)
    if date_to:
        invoices = invoices.filter(created_at__date__lte=date_to)
    headers = ['الحالة', 'العدد', 'الصافي', 'الضريبة', 'الإجمالي']
    status_labels = {
        'pending': 'في الانتظار',
        'submitted': 'تم الإرسال',
        'valid': 'مقبولة',
        'invalid': 'مرفوضة',
        'failed': 'فشل الإرسال',
    }
    rows = []
    for row in invoices.values('status').annotate(
        count=Count('id'), net=Sum('net_amount'), vat=Sum('total_vat_amount'), total=Sum('total_amount')
    ):
        label = status_labels.get(row['status'], row['status'])
        rows.append([label, str(row['count']), str(row['net'] or 0), str(row['vat'] or 0), str(row['total'] or 0)])
    if fmt == 'pdf':
        return export_to_pdf(f'ملخص الضرائب من {date_from} إلى {date_to}', headers, rows, 'tax_summary')
    return _export_simple_xlsx(headers, rows, 'tax_summary')


def _export_payroll_detail(request, date_from, date_to, fmt):
    year = request.GET.get('year', timezone.now().year)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = timezone.now().year
    month = request.GET.get('month', '')
    try:
        month = int(month) if month else None
    except (ValueError, TypeError):
        month = None
    salaries = Salary.objects.filter(year=year).select_related('employee', 'employee__department')
    if month:
        salaries = salaries.filter(month=month)
    headers = [
        'الموظف',
        'القسم',
        'الشهر',
        'الأساسي',
        'البدلات',
        'الإضافي',
        'المكافآت',
        'الخصومات',
        'التأمين',
        'الضريبة',
        'الصافي',
    ]
    rows = []
    for s in salaries:
        dept = s.employee.department.name if s.employee.department else '-'
        rows.append(
            [
                s.employee.full_name,
                dept,
                str(s.month),
                str(s.basic_salary),
                str(s.allowances),
                str(s.overtime),
                str(s.bonus),
                str(s.deductions),
                str(s.social_insurance),
                str(s.income_tax),
                str(s.net_salary),
            ]
        )
    if fmt == 'pdf':
        return export_to_pdf(f'تفصيلي الرواتب {year}', headers, rows, 'payroll_detail')
    return _export_simple_xlsx(headers, rows, 'payroll_detail')


# ============================================================
# NEW REPORTS - Detailed Reports
# ============================================================


@screen_permission_required('reports.report', 'view')
def ar_aging_report(request):
    today = timezone.now().date()
    raw_to = request.GET.get('date_to')
    date_to = _safe_parse_date(raw_to, 'date_to') if raw_to else None
    if date_to is None:
        date_to = today

    invoices = SalesInvoice.objects.filter(remaining_amount__gt=0, is_posted=True).select_related('customer')

    aging_data = []
    total_remaining = Decimal('0')
    bucket_current = Decimal('0')
    bucket_30 = Decimal('0')
    bucket_60 = Decimal('0')
    bucket_90 = Decimal('0')
    bucket_120 = Decimal('0')

    for inv in invoices:
        if inv.due_date:
            days_overdue = (date_to - inv.due_date).days
        else:
            days_overdue = (date_to - inv.date).days

        if days_overdue <= 0:
            bucket = 'current'
            bucket_current += inv.remaining_amount
        elif days_overdue <= 30:
            bucket = '1-30'
            bucket_30 += inv.remaining_amount
        elif days_overdue <= 60:
            bucket = '31-60'
            bucket_60 += inv.remaining_amount
        elif days_overdue <= 90:
            bucket = '61-90'
            bucket_90 += inv.remaining_amount
        else:
            bucket = '120+'
            bucket_120 += inv.remaining_amount

        aging_data.append(
            {
                'invoice': inv,
                'customer_name': inv.customer.name,
                'invoice_date': inv.date,
                'due_date': inv.due_date,
                'days_overdue': max(0, days_overdue),
                'total_amount': inv.total_amount,
                'paid_amount': inv.paid_amount,
                'remaining': inv.remaining_amount,
                'bucket': bucket,
            }
        )
        total_remaining += inv.remaining_amount

    aging_data.sort(key=lambda x: x['days_overdue'], reverse=True)

    context = {
        'date_to': date_to,
        'aging_data': aging_data,
        'total_remaining': total_remaining,
        'bucket_current': bucket_current,
        'bucket_30': bucket_30,
        'bucket_60': bucket_60,
        'bucket_90': bucket_90,
        'bucket_120': bucket_120,
    }
    return render(request, 'reports/ar_aging.html', context)


@screen_permission_required('reports.report', 'view')
def ap_aging_report(request):
    today = timezone.now().date()
    raw_to = request.GET.get('date_to')
    date_to = _safe_parse_date(raw_to, 'date_to') if raw_to else None
    if date_to is None:
        date_to = today

    invoices = PurchaseInvoice.objects.filter(remaining_amount__gt=0, is_posted=True).select_related('supplier')

    aging_data = []
    total_remaining = Decimal('0')
    bucket_current = Decimal('0')
    bucket_30 = Decimal('0')
    bucket_60 = Decimal('0')
    bucket_90 = Decimal('0')
    bucket_120 = Decimal('0')

    for inv in invoices:
        if inv.due_date:
            days_overdue = (date_to - inv.due_date).days
        else:
            days_overdue = (date_to - inv.date).days

        if days_overdue <= 0:
            bucket = 'current'
            bucket_current += inv.remaining_amount
        elif days_overdue <= 30:
            bucket = '1-30'
            bucket_30 += inv.remaining_amount
        elif days_overdue <= 60:
            bucket = '31-60'
            bucket_60 += inv.remaining_amount
        elif days_overdue <= 90:
            bucket = '61-90'
            bucket_90 += inv.remaining_amount
        else:
            bucket = '120+'
            bucket_120 += inv.remaining_amount

        aging_data.append(
            {
                'invoice': inv,
                'supplier_name': inv.supplier.name,
                'invoice_date': inv.date,
                'due_date': inv.due_date,
                'days_overdue': max(0, days_overdue),
                'total_amount': inv.total_amount,
                'paid_amount': inv.paid_amount,
                'remaining': inv.remaining_amount,
                'bucket': bucket,
            }
        )
        total_remaining += inv.remaining_amount

    aging_data.sort(key=lambda x: x['days_overdue'], reverse=True)

    context = {
        'date_to': date_to,
        'aging_data': aging_data,
        'total_remaining': total_remaining,
        'bucket_current': bucket_current,
        'bucket_30': bucket_30,
        'bucket_60': bucket_60,
        'bucket_90': bucket_90,
        'bucket_120': bucket_120,
    }
    return render(request, 'reports/ap_aging.html', context)


@screen_permission_required('reports.report', 'view')
@cache_page(120)
@vary_on_cookie
def inventory_report(request):
    warehouse_id = request.GET.get('warehouse')
    date_from, date_to = _get_date_range(request)

    warehouses = Warehouse.objects.filter(is_active=True)
    warehouse_products = WarehouseProduct.objects.select_related('warehouse', 'product').all()

    if warehouse_id:
        warehouse_products = warehouse_products.filter(warehouse_id=warehouse_id)

    movements = (
        StockMovement.objects.select_related('warehouse', 'product', 'to_warehouse')
        .filter(date__gte=date_from, date__lte=date_to)
        .order_by('-date')
    )

    low_stock = [wp for wp in warehouse_products if wp.is_low]

    total_stock_value = sum((wp.quantity * wp.product.purchase_price) for wp in warehouse_products)

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'warehouses': warehouses,
        'selected_warehouse': warehouse_id,
        'warehouse_products': warehouse_products,
        'movements': movements,
        'total_stock_value': total_stock_value,
        'low_stock': low_stock,
    }
    return render(request, 'reports/inventory_report.html', context)


@screen_permission_required('reports.report', 'view')
def stock_valuation_report(request):
    warehouse_id = request.GET.get('warehouse')
    warehouses = Warehouse.objects.filter(is_active=True)

    layers = (
        InventoryCostLayer.objects.filter(is_active=True, quantity_remaining__gt=0)
        .select_related('product', 'warehouse')
        .order_by('product__code', 'warehouse__name', 'date')
    )

    if warehouse_id:
        layers = layers.filter(warehouse_id=warehouse_id)

    product_summary = {}
    for layer in layers:
        key = (layer.product_id, layer.warehouse_id)
        if key not in product_summary:
            product_summary[key] = {
                'product': layer.product,
                'warehouse': layer.warehouse,
                'total_qty': Decimal('0'),
                'total_value': Decimal('0'),
                'layers': [],
            }
        product_summary[key]['total_qty'] += layer.quantity_remaining
        product_summary[key]['total_value'] += layer.total_cost
        product_summary[key]['layers'].append(layer)

    items = sorted(product_summary.values(), key=lambda x: x['product'].code)
    grand_total_value = sum(i['total_value'] for i in items)
    grand_total_qty = sum(i['total_qty'] for i in items)

    context = {
        'warehouses': warehouses,
        'selected_warehouse': warehouse_id,
        'items': items,
        'grand_total_value': grand_total_value,
        'grand_total_qty': grand_total_qty,
    }
    return render(request, 'reports/stock_valuation_report.html', context)


@screen_permission_required('reports.report', 'view')
def customer_statement(request):
    customer_id = request.GET.get('customer')
    date_from, date_to = _get_date_range(request)

    customers = Customer.objects.filter(is_active=True)
    customer = None
    invoices = []
    total_sales = Decimal('0')
    total_collected = Decimal('0')
    total_remaining = Decimal('0')

    if customer_id:
        customer = get_object_or_404(Customer, pk=customer_id)
        invoices = SalesInvoice.objects.filter(
            customer=customer, date__gte=date_from, date__lte=date_to, is_posted=True
        ).order_by('date')

        total_sales = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        total_collected = invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        total_remaining = total_sales - total_collected

    context = {
        'customers': customers,
        'selected_customer': customer_id,
        'customer': customer,
        'invoices': invoices,
        'date_from': date_from,
        'date_to': date_to,
        'total_sales': total_sales,
        'total_collected': total_collected,
        'total_remaining': total_remaining,
    }
    return render(request, 'reports/customer_statement.html', context)


@screen_permission_required('reports.report', 'view')
def supplier_statement(request):
    supplier_id = request.GET.get('supplier')
    date_from, date_to = _get_date_range(request)

    suppliers = Supplier.objects.filter(is_active=True)
    supplier = None
    invoices = []
    total_purchases = Decimal('0')
    total_paid = Decimal('0')
    total_remaining = Decimal('0')

    if supplier_id:
        supplier = get_object_or_404(Supplier, pk=supplier_id)
        invoices = PurchaseInvoice.objects.filter(
            supplier=supplier, date__gte=date_from, date__lte=date_to, is_posted=True
        ).order_by('date')

        total_purchases = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        total_paid = invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        total_remaining = total_purchases - total_paid

    context = {
        'suppliers': suppliers,
        'selected_supplier': supplier_id,
        'supplier': supplier,
        'invoices': invoices,
        'date_from': date_from,
        'date_to': date_to,
        'total_purchases': total_purchases,
        'total_paid': total_paid,
        'total_remaining': total_remaining,
    }
    return render(request, 'reports/supplier_statement.html', context)


@screen_permission_required('reports.report', 'view')
def daily_sales_report(request):
    date_from, date_to = _get_date_range(request)

    invoices = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True).order_by('date')

    daily_data = {}
    for inv in invoices:
        d = inv.date
        if d not in daily_data:
            daily_data[d] = {
                'date': d,
                'count': 0,
                'subtotal': Decimal('0'),
                'vat': Decimal('0'),
                'total': Decimal('0'),
                'collected': Decimal('0'),
                'remaining': Decimal('0'),
                'profit': Decimal('0'),
            }
        daily_data[d]['count'] += 1
        daily_data[d]['subtotal'] += inv.subtotal
        daily_data[d]['vat'] += inv.vat_amount
        daily_data[d]['total'] += inv.total_amount
        daily_data[d]['collected'] += inv.paid_amount
        daily_data[d]['remaining'] += inv.remaining_amount
        daily_data[d]['profit'] += inv.gross_profit

    daily_list = sorted(daily_data.values(), key=lambda x: x['date'])

    grand_total = {
        'count': sum(d['count'] for d in daily_list),
        'subtotal': sum(d['subtotal'] for d in daily_list),
        'vat': sum(d['vat'] for d in daily_list),
        'total': sum(d['total'] for d in daily_list),
        'collected': sum(d['collected'] for d in daily_list),
        'remaining': sum(d['remaining'] for d in daily_list),
        'profit': sum(d['profit'] for d in daily_list),
    }

    context = {'date_from': date_from, 'date_to': date_to, 'daily_list': daily_list, 'grand_total': grand_total}
    return render(request, 'reports/daily_sales.html', context)


@screen_permission_required('reports.report', 'view')
def daily_purchases_report(request):
    date_from, date_to = _get_date_range(request)

    invoices = PurchaseInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True).order_by('date')

    daily_data = {}
    for inv in invoices:
        d = inv.date
        if d not in daily_data:
            daily_data[d] = {
                'date': d,
                'count': 0,
                'subtotal': Decimal('0'),
                'vat': Decimal('0'),
                'total': Decimal('0'),
                'paid': Decimal('0'),
                'remaining': Decimal('0'),
                'withholding': Decimal('0'),
            }
        daily_data[d]['count'] += 1
        daily_data[d]['subtotal'] += inv.subtotal
        daily_data[d]['vat'] += inv.vat_amount
        daily_data[d]['total'] += inv.total_amount
        daily_data[d]['paid'] += inv.paid_amount
        daily_data[d]['remaining'] += inv.remaining_amount
        daily_data[d]['withholding'] += inv.withholding_tax_amount

    daily_list = sorted(daily_data.values(), key=lambda x: x['date'])

    grand_total = {
        'count': sum(d['count'] for d in daily_list),
        'subtotal': sum(d['subtotal'] for d in daily_list),
        'vat': sum(d['vat'] for d in daily_list),
        'total': sum(d['total'] for d in daily_list),
        'paid': sum(d['paid'] for d in daily_list),
        'remaining': sum(d['remaining'] for d in daily_list),
        'withholding': sum(d['withholding'] for d in daily_list),
    }

    context = {'date_from': date_from, 'date_to': date_to, 'daily_list': daily_list, 'grand_total': grand_total}
    return render(request, 'reports/daily_purchases.html', context)


@screen_permission_required('reports.report', 'view')
@cache_page(300)
@vary_on_cookie
def cash_flow_report(request):
    date_from, date_to = _get_date_range(request)

    sales_invoices = SalesInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True)
    purchase_invoices = PurchaseInvoice.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True)

    cash_in = sales_invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    cash_out = purchase_invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')

    from payment_receipts.models import PaymentReceipt

    receipts = PaymentReceipt.objects.filter(date__gte=date_from, date__lte=date_to, is_posted=True)
    collection_cash = receipts.filter(receipt_type='receipt', payment_method='cash').aggregate(t=Sum('amount'))[
        't'
    ] or Decimal('0')
    payment_cash = receipts.filter(receipt_type='payment', payment_method='cash').aggregate(t=Sum('amount'))[
        't'
    ] or Decimal('0')
    collection_bank = receipts.filter(receipt_type='receipt', payment_method='bank_transfer').aggregate(
        t=Sum('amount')
    )['t'] or Decimal('0')
    payment_bank = receipts.filter(receipt_type='payment', payment_method='bank_transfer').aggregate(t=Sum('amount'))[
        't'
    ] or Decimal('0')

    total_inflows = collection_cash + collection_bank + cash_in
    total_outflows = payment_cash + payment_bank + cash_out
    net_cash_flow = total_inflows - total_outflows

    bank_deposits = BankTransaction.objects.filter(
        date__gte=date_from, date__lte=date_to, transaction_type='deposit'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    bank_withdrawals = BankTransaction.objects.filter(
        date__gte=date_from, date__lte=date_to, transaction_type='withdrawal'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    return render(
        request,
        'reports/cash_flow.html',
        {
            'date_from': date_from,
            'date_to': date_to,
            'cash_in': cash_in,
            'cash_out': cash_out,
            'collection_cash': collection_cash,
            'payment_cash': payment_cash,
            'collection_bank': collection_bank,
            'payment_bank': payment_bank,
            'total_inflows': total_inflows,
            'total_outflows': total_outflows,
            'net_cash_flow': net_cash_flow,
            'bank_deposits': bank_deposits,
            'bank_withdrawals': bank_withdrawals,
        },
    )


# ============================================================
# M9 - New Read-Only Reports
# ============================================================


@screen_permission_required('reports.report', 'view')
def budget_vs_actual(request):
    """تقرير الموازنة مقابل الفعلي لفترة مالية/مركز تكلفة."""
    year = request.GET.get('year', timezone.now().year)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = timezone.now().year

    month = request.GET.get('month', '')
    try:
        month = int(month) if month else None
    except (ValueError, TypeError):
        month = None

    cost_center_id = request.GET.get('cost_center') or None

    budgets = Budget.objects.filter(year=year)
    if month:
        budgets = budgets.filter(month=month)
    if cost_center_id:
        budgets = budgets.filter(cost_center_id=cost_center_id)
    budgets = budgets.select_related('account', 'account__account_type', 'cost_center').order_by('account__code')

    # تحديد نطاق التاريخ للنشاط الفعلي
    if month:
        date_from = timezone.now().replace(year=year, month=month, day=1).date()
        if month == 12:
            date_to = date_from.replace(year=year + 1, month=1, day=1) - timedelta(days=1)
        else:
            date_to = date_from.replace(month=month + 1, day=1) - timedelta(days=1)
    else:
        date_from = timezone.now().replace(year=year, month=1, day=1).date()
        date_to = date_from.replace(month=12, day=31)

    activity = _posted_lines_in_range(date_from, date_to)

    total_budgeted = Decimal('0')
    total_actual = Decimal('0')
    total_variance = Decimal('0')

    rows = []
    for b in budgets:
        acc_type = b.account.account_type.account_type if b.account.account_type else 'expense'
        acc_act = activity.get(b.account_id, {'debit': Decimal('0'), 'credit': Decimal('0')})
        actual = _period_net(acc_act, acc_type)
        planned = b.budgeted_amount
        variance = actual - planned
        variance_pct = round((variance / planned * 100), 1) if planned else Decimal('0')
        rows.append(
            {
                'account_code': b.account.code,
                'account_name': b.account.name,
                'planned': planned,
                'actual': actual,
                'variance': variance,
                'variance_pct': variance_pct,
            }
        )
        total_budgeted += planned
        total_actual += actual
        total_variance += variance

    total_variance_pct = round((total_variance / total_budgeted * 100), 1) if total_budgeted else Decimal('0')

    cost_centers = CostCenter.objects.filter(is_active=True)

    context = {
        'year': year,
        'month': month,
        'years': range(timezone.now().year - 5, timezone.now().year + 1),
        'months': [
            (m, label)
            for m, label in [
                (1, 'يناير'),
                (2, 'فبراير'),
                (3, 'مارس'),
                (4, 'أبريل'),
                (5, 'مايو'),
                (6, 'يونيو'),
                (7, 'يوليو'),
                (8, 'أغسطس'),
                (9, 'سبتمبر'),
                (10, 'أكتوبر'),
                (11, 'نوفمبر'),
                (12, 'ديسمبر'),
            ]
        ],
        'cost_centers': cost_centers,
        'selected_cost_center': cost_center_id,
        'rows': rows,
        'date_from': date_from,
        'date_to': date_to,
        'total_budgeted': total_budgeted,
        'total_actual': total_actual,
        'total_variance': total_variance,
        'total_variance_pct': total_variance_pct,
    }
    return render(request, 'reports/budget_vs_actual.html', context)


@screen_permission_required('reports.report', 'view')
def bank_reconciliation_statement(request):
    """كشف التسوية البنكية: رصيد البنك مقابل رصيد الدفتر والأرصدة غير المطابقة."""
    date_from, date_to = _get_date_range(request)

    banks = Bank.objects.filter(is_active=True).select_related('account', 'account__account_type')

    # رصيد الدفتر من الاستاذ العام لكل حساب بنكي
    book_accounts = [b.account for b in banks if b.account]
    balances = _balances_as_of(book_accounts, date_to) if book_accounts else {}

    # الأرصدة غير المطابقة (الشيكات غير المحصلة)
    outstanding_cheques = (
        Cheque.objects.filter(status__in=['pending', 'deposited'], due_date__lte=date_to)
        .select_related('customer', 'supplier', 'bank_account')
        .order_by('due_date')
    )

    # تجميع بنود كشف البنك لحساب الرصيد طبقاً للبيان
    statement_items = (
        BankStatementItem.objects.filter(transaction_date__gte=date_from, transaction_date__lte=date_to)
        .values('bank_account_id')
        .annotate(credits=Sum('credit_amount'), debits=Sum('debit_amount'))
    )
    statement_map = {
        r['bank_account_id']: (r['credits'] or Decimal('0')) - (r['debits'] or Decimal('0')) for r in statement_items
    }

    # تجميع الشيكات غير المطابقة حسب الحساب البنكي (GL)
    cheque_by_account = {}
    for c in outstanding_cheques:
        key = c.bank_account_id
        if key not in cheque_by_account:
            cheque_by_account[key] = []
        cheque_by_account[key].append(c)

    total_book = Decimal('0')
    total_statement = Decimal('0')
    total_outstanding = Decimal('0')
    total_diff = Decimal('0')

    bank_rows = []
    for bank in banks:
        book_balance = balances.get(bank.account_id, Decimal('0')) if bank.account else Decimal('0')
        statement_balance = statement_map.get(bank.id, Decimal('0'))
        cheques = cheque_by_account.get(bank.account_id, []) if bank.account else []
        outstanding_total = sum((c.amount for c in cheques), Decimal('0'))
        reconciled_balance = book_balance - outstanding_total
        diff = book_balance - statement_balance
        bank_rows.append(
            {
                'bank': bank,
                'book_balance': book_balance,
                'statement_balance': statement_balance,
                'outstanding_cheques': cheques,
                'outstanding_total': outstanding_total,
                'reconciled_balance': reconciled_balance,
                'diff': diff,
            }
        )
        total_book += book_balance
        total_statement += statement_balance
        total_outstanding += outstanding_total
        total_diff += diff

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'banks': bank_rows,
        'outstanding_cheques': outstanding_cheques,
        'total_book': total_book,
        'total_statement': total_statement,
        'total_outstanding': total_outstanding,
        'total_diff': total_diff,
    }
    return render(request, 'reports/bank_reconciliation_statement.html', context)


@screen_permission_required('reports.report', 'view')
def tax_summary(request):
    """ملخص الضرائب الموحد: تجميع الفواتير الضريبية حسب الحالة وأرصدة ضريبة المبيعات/المشتريات."""
    date_from, date_to = _get_date_range(request)

    invoices = TaxInvoice.objects.all()
    if date_from:
        invoices = invoices.filter(created_at__date__gte=date_from)
    if date_to:
        invoices = invoices.filter(created_at__date__lte=date_to)

    # تجميع حسب الحالة
    status_order = ['pending', 'submitted', 'valid', 'invalid', 'failed']
    status_labels = {
        'pending': 'في الانتظار',
        'submitted': 'تم الإرسال',
        'valid': 'مقبولة (صالحة)',
        'invalid': 'مرفوضة',
        'failed': 'فشل الإرسال',
    }
    agg = {}
    for row in invoices.values('status').annotate(
        count=Count('id'), net=Sum('net_amount'), vat=Sum('total_vat_amount'), total=Sum('total_amount')
    ):
        agg[row['status']] = {
            'count': row['count'],
            'net': row['net'] or Decimal('0'),
            'vat': row['vat'] or Decimal('0'),
            'total': row['total'] or Decimal('0'),
        }
    status_rows = []
    for s in status_order:
        row = agg.get(s, {'count': 0, 'net': Decimal('0'), 'vat': Decimal('0'), 'total': Decimal('0')})
        status_rows.append(
            {
                'status': s,
                'label': status_labels.get(s, s),
                'count': row['count'],
                'net': row['net'],
                'vat': row['vat'],
                'total': row['total'],
            }
        )

    total_invoices = invoices.count()
    total_net = invoices.aggregate(t=Sum('net_amount'))['t'] or Decimal('0')
    total_vat = invoices.aggregate(t=Sum('total_vat_amount'))['t'] or Decimal('0')
    total_amount = invoices.aggregate(t=Sum('total_amount'))['t'] or Decimal('0')

    # ربط ضريبة المبيعات/المشتريات (أسلوب الإقرار)
    vat_output = SalesInvoice.objects.filter(
        date__gte=date_from, date__lte=date_to, is_tax_invoice=True, is_posted=True
    ).aggregate(t=Sum('vat_amount'))['t'] or Decimal('0')
    vat_input = PurchaseInvoice.objects.filter(
        date__gte=date_from, date__lte=date_to, is_tax_invoice=True, is_posted=True
    ).aggregate(t=Sum('vat_amount'))['t'] or Decimal('0')
    vat_payable = vat_output - vat_input

    eta_connections = ETAConnection.objects.filter(is_active=True)

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'status_rows': status_rows,
        'status_order': status_order,
        'total_invoices': total_invoices,
        'total_net': total_net,
        'total_vat': total_vat,
        'total_amount': total_amount,
        'vat_output': vat_output,
        'vat_input': vat_input,
        'vat_payable': vat_payable,
        'eta_connections': eta_connections,
    }
    return render(request, 'reports/tax_summary.html', context)


@screen_permission_required('reports.report', 'view')
def payroll_detail(request):
    """تقرير تفصيلي للرواتب: لكل مسير راتب (موظف، قسم، أساسي، بدلات، خصومات، صافي)."""
    year = request.GET.get('year', timezone.now().year)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = timezone.now().year

    month = request.GET.get('month', '')
    try:
        month = int(month) if month else None
    except (ValueError, TypeError):
        month = None

    salaries = Salary.objects.filter(year=year).select_related('employee', 'employee__department')
    if month:
        salaries = salaries.filter(month=month)
    salaries = salaries.order_by('employee__employee_number', 'month')

    total_basic = Decimal('0')
    total_allowances = Decimal('0')
    total_overtime = Decimal('0')
    total_bonus = Decimal('0')
    total_deductions = Decimal('0')
    total_social = Decimal('0')
    total_tax = Decimal('0')
    total_net = Decimal('0')

    rows = []
    for s in salaries:
        rows.append(
            {
                'employee': s.employee,
                'department': s.employee.department.name if s.employee.department else '-',
                'month': s.month,
                'basic': s.basic_salary,
                'allowances': s.allowances,
                'overtime': s.overtime,
                'bonus': s.bonus,
                'deductions': s.deductions,
                'social_insurance': s.social_insurance,
                'income_tax': s.income_tax,
                'net': s.net_salary,
                'is_paid': s.is_paid,
            }
        )
        total_basic += s.basic_salary
        total_allowances += s.allowances
        total_overtime += s.overtime
        total_bonus += s.bonus
        total_deductions += s.deductions
        total_social += s.social_insurance
        total_tax += s.income_tax
        total_net += s.net_salary

    context = {
        'year': year,
        'month': month,
        'years': range(timezone.now().year - 5, timezone.now().year + 1),
        'months': [
            (m, label)
            for m, label in [
                (1, 'يناير'),
                (2, 'فبراير'),
                (3, 'مارس'),
                (4, 'أبريل'),
                (5, 'مايو'),
                (6, 'يونيو'),
                (7, 'يوليو'),
                (8, 'أغسطس'),
                (9, 'سبتمبر'),
                (10, 'أكتوبر'),
                (11, 'نوفمبر'),
                (12, 'ديسمبر'),
            ]
        ],
        'rows': rows,
        'total_basic': total_basic,
        'total_allowances': total_allowances,
        'total_overtime': total_overtime,
        'total_bonus': total_bonus,
        'total_deductions': total_deductions,
        'total_social': total_social,
        'total_tax': total_tax,
        'total_net': total_net,
    }
    return render(request, 'reports/payroll_detail.html', context)
