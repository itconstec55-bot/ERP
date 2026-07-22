import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse

from accounts.models import Account, AccountType, JournalEntry, JournalEntryLine
from assets.models import Asset, AssetCategory, DepreciationEntry
from bank_reconciliation.models import BankStatementItem
from budget.models import Budget, CostCenter
from cheques.models import Cheque
from common.utils import parse_date_range
from hr.models import Department, Employee, Salary
from purchases.models import Product, PurchaseInvoice, Supplier
from sales.models import Customer, SalesInvoice, SalesInvoiceLine
from tax_invoices.models import ETAConnection, TaxInvoice
from treasury.models import Bank, BankTransaction, Safe, SafeTransaction
from warehouses.models import InventoryCostLayer, StockMovement, Warehouse, WarehouseProduct

# ──────────────────── Fixtures ────────────────────

@pytest.fixture
def user(db):
    """إنشاء مستخدم مسؤول للاختبارات"""
    return User.objects.create_superuser(
        'testadmin', 'test@test.com', 'pass123', is_staff=True, is_superuser=True
    )


@pytest.fixture
def anon_client():
    """عميل غير مصادق عليه"""
    return Client()



@pytest.fixture
def auth_client(user):
    """عميل مصادق عليه بالمسؤول"""
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def account_type_asset(db):
    """نوع حساب أصول"""
    return AccountType.objects.create(name='أصول متداولة', code='A1', account_type='asset')


@pytest.fixture
def account_type_liability(db):
    """نوع حساب خصوم"""
    return AccountType.objects.create(name='خصوم متداولة', code='L1', account_type='liability')


@pytest.fixture
def account_type_equity(db):
    """نوع حساب حقوق ملكية"""
    return AccountType.objects.create(name='حقوق ملكية', code='E1', account_type='equity')

@pytest.fixture
def account_type_revenue(db):
    """نوع حساب إيرادات"""
    return AccountType.objects.create(name='إيرادات المبيعات', code='R1', account_type='revenue')

@pytest.fixture
def account_type_expense(db):
    """نوع حساب مصروفات"""
    return AccountType.objects.create(name='مصروفات تشغيلية', code='X1', account_type='expense')

@pytest.fixture
def asset_account(account_type_asset):
    """حساب أصول بنوك"""
    return Account.objects.create(
        code='1100', name='البنوك', account_type=account_type_asset,
        opening_balance=Decimal('50000'), is_active=True, is_bank=True,
    )

@pytest.fixture
def expense_account(account_type_expense):
    """حساب مصروفات"""
    return Account.objects.create(
        code='5100', name='مصروفات إيجار', account_type=account_type_expense,
        opening_balance=Decimal('0'), is_active=True,
    )

@pytest.fixture
def revenue_account(account_type_revenue):
    """حساب إيرادات"""
    return Account.objects.create(
        code='4100', name='إيرادات مبيعات', account_type=account_type_revenue,
        opening_balance=Decimal('0'), is_active=True,
    )

@pytest.fixture
def liability_account(account_type_liability):
    """حساب خصوم"""
    return Account.objects.create(
        code='2100', name='حساب الموردين', account_type=account_type_liability,
        opening_balance=Decimal('0'), is_active=True,
    )

@pytest.fixture
def equity_account(account_type_equity):
    """حساب حقوق ملكية"""
    return Account.objects.create(
        code='3100', name='رأس المال', account_type=account_type_equity,
        opening_balance=Decimal('100000'), is_active=True,
    )

@pytest.fixture
def customer(db):
    """عميل تجريبي"""
    return Customer.objects.create(code='C001', name='شركة الاختبار', is_active=True)

@pytest.fixture
def supplier(db):
    """مورد تجريبي"""
    return Supplier.objects.create(code='S001', name='مورد الاختبار', is_active=True)

@pytest.fixture
def product(db):
    """منتج تجريبي"""
    return Product.objects.create(
        code='P001', name='منتج اختباري', is_active=True,
        purchase_price=Decimal('100'), selling_price=Decimal('150'),
    )

@pytest.fixture
def warehouse(db):
    """مخزن تجريبي"""
    return Warehouse.objects.create(code='W001', name='المخزن الرئيسي', is_active=True)

@pytest.fixture
def bank(db):
    """بنك تجريبي"""
    return Bank.objects.create(name='البنك الأهلي', account_number='123456', current_balance=Decimal('100000'), is_active=True)

@pytest.fixture
def safe(db):
    """خزينة تجريبية"""
    return Safe.objects.create(name='خزينة المكتب', current_balance=Decimal('50000'), is_active=True)

@pytest.fixture
def today():
    """اليوم الحالي"""
    return date.today()

@pytest.fixture
def date_range(today):
    """نطاق تاريخ: أول الشهر إلى اليوم"""
    return today.replace(day=1), today

@pytest.fixture
def sales_invoice(db, customer, today):
    """فاتورة مبيعات مرحلة"""
    inv = SalesInvoice.objects.create(
        invoice_number='SI-TEST-001', customer=customer, date=today,
        subtotal=Decimal('10000'), vat_amount=Decimal('1400'),
        total_amount=Decimal('11400'), paid_amount=Decimal('5000'),
        remaining_amount=Decimal('6400'),
        cost_of_goods=Decimal('6000'), gross_profit=Decimal('4000'),
        is_posted=True, is_tax_invoice=True,
        due_date=today + timedelta(days=30),
    )
    return inv

@pytest.fixture
def purchase_invoice(db, supplier, today):
    """فاتورة مشتريات مرحلة"""
    return PurchaseInvoice.objects.create(
        invoice_number='PI-TEST-001', supplier=supplier, date=today,
        subtotal=Decimal('8000'), vat_amount=Decimal('1120'),
        total_amount=Decimal('9120'), paid_amount=Decimal('3000'),
        remaining_amount=Decimal('6120'),
        is_posted=True, is_tax_invoice=True,
        due_date=today + timedelta(days=15),
    )

@pytest.fixture
def journal_entry_lines(db, asset_account, expense_account, revenue_account, today):
    """قيود محاسبية مرحلة"""
    je = JournalEntry.objects.create(
        entry_number='JE-TEST-001', entry_type='general',
        date=today, description='قيد اختباري', is_posted=True,
    )
    JournalEntryLine.objects.create(
        journal_entry=je, account=asset_account,
        debit=Decimal('10000'), credit=Decimal('0'),
        description='مدين أصول',
    )
    JournalEntryLine.objects.create(
        journal_entry=je, account=revenue_account,
        debit=Decimal('0'), credit=Decimal('10000'),
        description='دائن إيرادات',
    )
    je.calculate_totals()
    je.save(update_fields=['total_debit', 'total_credit'])
    return je

@pytest.fixture
def department(db):
    """قسم تجريبي"""
    return Department.objects.create(name='قسم الاختبار', is_active=True)

@pytest.fixture
def employee(db, department):
    """موظف تجريبي"""
    return Employee.objects.create(
        employee_number='EMP001', first_name='أحمد', last_name='محمد',
        national_id='12345678901234', gender='male', position='محاسب',
        hire_date=date(2020, 1, 1), department=department, status='active',
    )

@pytest.fixture
def salary_record(db, employee):
    """سجل راتب تجريبي"""
    return Salary.objects.create(
        employee=employee, month=1, year=2026,
        basic_salary=Decimal('5000'), allowances=Decimal('1000'),
        overtime=Decimal('500'), bonus=Decimal('200'),
        deductions=Decimal('300'), social_insurance=Decimal('200'),
        income_tax=Decimal('150'), net_salary=Decimal('6050'),
    )

@pytest.fixture
def asset_category(db):
    """تصنيف أصول"""
    return AssetCategory.objects.create(name='أجهزة كمبيوتر', depreciation_rate=Decimal('25'))

@pytest.fixture
def fixed_asset(db, asset_category):
    """أصل ثابت"""
    a = Asset.objects.create(
        code='A-001', name='كمبيوتر مكتبي', category=asset_category,
        purchase_date=date(2024, 1, 1), purchase_price=Decimal('20000'),
        useful_life_years=5, status='active', is_active=True,
        accumulated_depreciation=Decimal('5000'),
    )
    a.net_book_value = a.purchase_price - a.accumulated_depreciation
    a.save(update_fields=['net_book_value'])
    return a

@pytest.fixture
def eta_connection(db):
    """إعداد اتصال الفاتورة الإلكترونية"""
    return ETAConnection.objects.create(name='اختبار', environment='sandbox', is_active=True)

@pytest.fixture
def tax_invoice(db, eta_connection):
    """فاتورة ضريبية"""
    return TaxInvoice.objects.create(
        tax_invoice_number='TI-001', connection=eta_connection,
        status='valid', net_amount=Decimal('10000'),
        total_vat_amount=Decimal('1400'), total_amount=Decimal('11400'),
    )

@pytest.fixture
def cost_center(db):
    """مركز تكلفة"""
    return CostCenter.objects.create(code='CC01', name='الإدارة', is_active=True)

@pytest.fixture
def sales_invoice_with_line(db, customer, product, today):
    """فاتورة مبيعات مرحلة مع بند"""
    inv = SalesInvoice.objects.create(
        invoice_number='SI-LINE-001', customer=customer, date=today,
        subtotal=Decimal('5000'), vat_amount=Decimal('700'),
        total_amount=Decimal('5700'), paid_amount=Decimal('5700'),
        remaining_amount=Decimal('0'),
        cost_of_goods=Decimal('3000'), gross_profit=Decimal('2000'),
        is_posted=True, is_tax_invoice=True,
    )
    SalesInvoiceLine.objects.create(
        invoice=inv, product=product, quantity=Decimal('50'),
        unit_price=Decimal('100'), cost_price=Decimal('60'),
        total_price=Decimal('5000'), cost_total=Decimal('3000'),
    )
    return inv

@pytest.fixture
def warehouse_product(db, warehouse, product):
    """منتج في المخزن"""
    return WarehouseProduct.objects.create(
        warehouse=warehouse, product=product,
        quantity=Decimal('100'), minimum_quantity=Decimal('20'),
        maximum_quantity=Decimal('200'),
    )

@pytest.fixture
def cost_layer(db, warehouse, product):
    """طبقة تكلفة مخزون"""
    return InventoryCostLayer.objects.create(
        product=product, warehouse=warehouse,
        quantity_remaining=Decimal('50'), unit_cost=Decimal('100'),
        total_cost=Decimal('5000'), date=date.today(), is_active=True,
    )

@pytest.fixture
def budget_item(db, expense_account, cost_center):
    """عنصر موازنة"""
    return Budget.objects.create(
        name='موازنة الإيجار', account=expense_account,
        cost_center=cost_center, year=2026, month=1,
        budgeted_amount=Decimal('10000'),
    )


# ──────────────────── 1. Dashboard View Tests ────────────────────
class TestDashboardView:
    """اختبارات لوحة التحكم الرئيسية"""

    def test_dashboard_requires_login(self, anon_client):
        """يجب أن يتطلب تسجيل الدخول"""
        resp = anon_client.get(reverse('reports:report_list'))
        assert resp.status_code == 302

    def test_dashboard_renders(self, auth_client):
        """عرض لوحة التحكم بنجاح"""
        resp = auth_client.get(reverse('reports:report_list'))
        assert resp.status_code == 200

    def test_dashboard_with_empty_data(self, auth_client):
        """لوحة التحكم مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:report_list'))
        assert resp.status_code == 200

    def test_dashboard_lists_report_links(self, auth_client):
        """التأكد من وجود روابط التقارير في الصفحة"""
        resp = auth_client.get(reverse('reports:report_list'))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'reports' in content or 'تقرير' in content

    def test_dashboard_data_aggregation(self, auth_client, sales_invoice, purchase_invoice):
        """اختبار تجميع بيانات لوحة التحكم"""
        resp = auth_client.get(reverse('dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'today' in c
        assert 'total_purchases_month' in c
        assert 'total_sales_month' in c
        assert 'total_profit_month' in c
        assert 'profit_margin' in c
        assert c['total_sales_month'] >= Decimal('0')
        assert c['total_purchases_month'] >= Decimal('0')

    def test_dashboard_recent_invoices(self, auth_client, sales_invoice, purchase_invoice):
        """اختبار الفواتير الأخيرة في لوحة التحكم"""
        resp = auth_client.get(reverse('dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'recent_sales' in c
        assert 'recent_purchases' in c
        assert len(c['recent_sales']) <= 5
        assert len(c['recent_purchases']) <= 5

    def test_dashboard_financial_metrics(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """اختبار المقاييس المالية في لوحة التحكم"""
        resp = auth_client.get(reverse('dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'suppliers_count' in c
        assert 'customers_count' in c
        assert 'employees_count' in c
        assert 'products_count' in c
        assert 'assets_count' in c
        assert 'total_bank_balance' in c
        assert 'total_safe_balance' in c

    def test_dashboard_card_metrics(self, auth_client, sales_invoice, purchase_invoice):
        """اختبار مقاييس البطاقات في لوحة التحكم"""
        resp = auth_client.get(reverse('dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'low_stock_count' in c
        assert 'overdue_count' in c
        assert 'overdue_ap_count' in c

    def test_dashboard_chart_data(self, auth_client, sales_invoice, purchase_invoice):
        """اختبار بيانات الرسوم البيانية في لوحة التحكم"""
        resp = auth_client.get(reverse('dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'chart_labels' in c
        assert 'chart_sales' in c
        assert 'chart_purchases' in c
        assert len(c['chart_labels']) > 0

    def test_dashboard_age_buckets(self, auth_client, sales_invoice, purchase_invoice):
        """اختبار أرصدة الذمم المدينة والدائنة في لوحة التحكم"""
        resp = auth_client.get(reverse('dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'top_suppliers_debt' in c
        assert 'top_customers_debt' in c

    def test_dashboard_approval_counts(self, auth_client, sales_invoice, purchase_invoice):
        """اختبار طلبات الموافقة في لوحة التحكم"""
        resp = auth_client.get(reverse('dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'pending_approvals_pi' in c
        assert 'pending_approvals_si' in c
        assert 'recent_journal_entries' in c

    def test_dashboard_growth_metrics(self, auth_client, sales_invoice, purchase_invoice):
        """اختبار مقاييس النمو في لوحة التحكم"""
        resp = auth_client.get(reverse('dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'profit_margin' in c
        if c.get('total_sales_month', 0) > 0:
            assert c['profit_margin'] >= 0


# ──────────────────── 2. Financial Dashboard View Tests ────────────────────
class TestFinancialDashboardView:
    """اختبارات لوحة التحكم المالية"""

    def test_financial_dashboard_requires_login(self, anon_client):
        """لوحة التحكم المالية تتطلب تسجيل الدخول"""
        resp = anon_client.get(reverse('reports:financial_dashboard'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_financial_dashboard_render(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """عرض لوحة التحكم المالية بنجاح"""
        resp = auth_client.get(reverse('reports:financial_dashboard'))
        assert resp.status_code == 200
        assert 'today' in resp.context
        assert 'cash_position' in resp.context
        assert 'total_ar' in resp.context
        assert 'total_ap' in resp.context

    @pytest.mark.django_db
    def test_financial_dashboard_with_empty_data(self, auth_client):
        """لوحة التحكم المالية مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:financial_dashboard'))
        assert resp.status_code == 200
        assert resp.context['cash_position'] == 0

    @pytest.mark.django_db
    def test_financial_dashboard_data_aggregation(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """اختبار تجميع بيانات لوحة التحكم المالية"""
        resp = auth_client.get(reverse('reports:financial_dashboard'))
        assert resp.status_code == 200
        assert resp.context['total_ar'] >= 0
        assert resp.context['total_ap'] >= 0

    @pytest.mark.django_db
    def test_financial_dashboard_chart_data(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """لوحة التحكم المالية تحتوي على بيانات الرسوم البيانية"""
        resp = auth_client.get(reverse('reports:financial_dashboard'))
        assert resp.status_code == 200
        c = resp.context
        assert 'today' in c
        assert 'cash_position' in c
        assert 'total_ar' in c
        assert 'total_ap' in c


# ──────────────────── 3. Workflow Tracker View Tests ────────────────────
class TestWorkflowTrackerView:
    """اختبارات شاشة تتبع سير العمل"""

    def test_workflow_tracker_requires_login(self, anon_client):
        """شاشة تتبع سير العمل تتطلب تسجيل الدخول"""
        resp = anon_client.get(reverse('reports:workflow_tracker'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_workflow_tracker_render(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """عرض شاشة تتبع سير العمل بنجاح"""
        resp = auth_client.get(reverse('reports:workflow_tracker'))
        assert resp.status_code == 200
        assert 'today' in resp.context
        assert 'stages' in resp.context
        assert len(resp.context['stages']) >= 4

    @pytest.mark.django_db
    def test_workflow_tracker_data_counts(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """شاشة تتبع سير العمل تعرض أعداد سير العمل"""
        resp = auth_client.get(reverse('reports:workflow_tracker'))
        assert resp.status_code == 200
        total_sales = sum(s['count'] for s in resp.context['stages'][1]['steps'] if s['name'] == 'فواتير المبيعات')
        total_purchases = sum(s['count'] for s in resp.context['stages'][0]['steps'] if s['name'] == 'فواتير المشتريات')
        assert total_sales >= 1 or total_purchases >= 1

    @pytest.mark.django_db
    def test_workflow_tracker_with_empty_data(self, auth_client):
        """شاشة تتبع سير العمل مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:workflow_tracker'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_workflow_tracker_real_data(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines, department, employee):
        """شاشة تتبع سير العمل مع بيانات واقعية"""
        resp = auth_client.get(reverse('reports:workflow_tracker'))
        assert resp.status_code == 200
        stages = resp.context['stages']
        for stage in stages:
            for step in stage['steps']:
                assert 'name' in step
                assert 'count' in step or step['count'] == 0


# ──────────────────── 4. Report List View Tests ────────────────────
class TestReportListView:
    """اختبارات صفحة قائمة التقارير"""

    def test_report_list_requires_login(self, anon_client):
        """صفحة قائمة التقارير تتطلب تسجيل الدخول"""
        resp = anon_client.get(reverse('reports:report_list'))
        assert resp.status_code == 302

    def test_report_list_render(self, auth_client):
        """عرض قائمة التقارير بنجاح"""
        resp = auth_client.get(reverse('reports:report_list'))
        assert resp.status_code == 200
        assert resp.content

    def test_report_list_groups(self, auth_client):
        """قائمة التقارير تحتوي على روابط للمجموعات"""
        resp = auth_client.get(reverse('reports:report_list'))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'تقرير' in content or 'Report' in content


# ──────────────────── 5. Balance Sheet View Tests ────────────────────
class TestBalanceSheetView:
    """اختبارات الميزانية العمومية"""

    def test_balance_sheet_requires_login(self, anon_client):
        """الميزانية العمومية تتطلب تسجيل الدخول"""
        resp = anon_client.get(reverse('reports:balance_sheet'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_balance_sheet_render(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """عرض الميزانية العمومية بنجاح"""
        resp = auth_client.get(reverse('reports:balance_sheet'))
        assert resp.status_code == 200
        assert 'current_assets' in resp.context
        assert 'total_assets' in resp.context
        assert 'current_liabilities' in resp.context
        assert 'total_liabilities' in resp.context
        assert 'total_equity' in resp.context
        assert 'net_profit' in resp.context

    @pytest.mark.django_db
    def test_balance_sheet_with_empty_data(self, auth_client):
        """الميزانية العمومية مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:balance_sheet'))
        assert resp.status_code == 200
        assert resp.context['total_assets'] == 0

    @pytest.mark.django_db
    def test_balance_sheet_with_sample_data(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """الميزانية العمومية مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:balance_sheet'))
        assert resp.status_code == 200
        assert resp.context['total_assets'] >= 0
        assert resp.context['total_liabilities'] >= 0

    @pytest.mark.django_db
    def test_balance_sheet_date_range(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """الميزانية العمومية مع نطاق تاريخ محدد"""
        df, dt = date(2026, 1, 1), date(2026, 1, 31)
        resp = auth_client.get(reverse('reports:balance_sheet'), {'date_from': df, 'date_to': dt})
        assert resp.status_code == 200
        assert resp.context['date_from'] == df
        assert resp.context['date_to'] == dt

    @pytest.mark.django_db
    def test_balance_sheet_template_context(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """اختبار سياق قالب الميزانية العمومية"""
        resp = auth_client.get(reverse('reports:balance_sheet'))
        assert resp.status_code == 200
        context = resp.context
        assert 'current_assets' in context
        assert 'non_current_assets' in context
        assert 'current_liabilities' in context
        assert 'non_current_liabilities' in context
        assert 'equity_accounts' in context


# ──────────────────── 6. Trial Balance Report View Tests ────────────────────
class TestTrialBalanceReportView:
    """اختبارات ميزان المراجعة"""

    def test_trial_balance_requires_login(self, anon_client):
        """ميزان المراجعة يتطلب تسجيل الدخول"""
        resp = anon_client.get(reverse('reports:trial_balance_report'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_trial_balance_render(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """عرض ميزان المراجعة بنجاح"""
        resp = auth_client.get(reverse('reports:trial_balance_report'))
        assert resp.status_code == 200
        assert 'accounts' in resp.context
        assert 'total_debit' in resp.context
        assert 'total_credit' in resp.context

    @pytest.mark.django_db
    def test_trial_balance_data_counts(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines, account_type_revenue, account_type_expense):
        """ميزان المراجعة يعرض الحسابات وأنها متساوية"""
        resp = auth_client.get(reverse('reports:trial_balance_report'))
        assert resp.status_code == 200
        assert resp.context['total_debit'] == resp.context['total_credit']
        assert len(resp.context['accounts']) >= 2

    @pytest.mark.django_db
    def test_trial_balance_with_empty_data(self, auth_client):
        """ميزان المراجعة مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:trial_balance_report'))
        assert resp.status_code == 200
        assert resp.context['total_debit'] == 0
        assert resp.context['total_credit'] == 0

    @pytest.mark.django_db
    def test_trial_balance_with_sample_data(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """ميزان المراجعة مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:trial_balance_report'))
        assert resp.status_code == 200
        assert resp.context['total_debit'] >= 0
        assert resp.context['total_credit'] >= 0

    @pytest.mark.django_db
    def test_trial_balance_with_date_range(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """ميزان المراجعة مع نطاق تاريخ محدد"""
        df, dt = date(2026, 1, 1), date(2026, 1, 31)
        resp = auth_client.get(reverse('reports:trial_balance_report'), {'date_from': df, 'date_to': dt})
        assert resp.status_code == 200
        assert resp.context['date_from'] == df
        assert resp.context['date_to'] == dt

    @pytest.mark.django_db
    def test_trial_balance_view_details(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """ميزان المراجعة مع تفاصيل الوحدات"""
        resp = auth_client.get(reverse('reports:trial_balance_report'))
        assert resp.status_code == 200
        accounts = resp.context['accounts']
        for acc in accounts:
            assert 'code' in dir(acc)
            assert 'name' in dir(acc)
            assert 'current_balance' in dir(acc)


# ──────────────────── 7. General Ledger View Tests ────────────────────
class TestGeneralLedgerView:
    """اختبارات دفتر الأستاذ العام"""

    def test_general_ledger_requires_login(self, anon_client):
        """دفتر الأستاذ العام يتطلب تسجيل الدخول"""
        resp = anon_client.get(reverse('reports:general_ledger'))
        assert resp.status_code == 302

    def test_general_ledger_with_account(self, auth_client, asset_account):
        """دفتر الأستاذ العام مع حساب محدد"""
        resp = auth_client.get(reverse('reports:general_ledger'), {'account': asset_account.id})
        assert resp.status_code == 200
        assert 'selected_account' in resp.context
        assert resp.context['selected_account'] == str(asset_account.id)

    @pytest.mark.django_db
    def test_general_ledger_render(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """عرض دفتر الأستاذ العام بنجاح"""
        resp = auth_client.get(reverse('reports:general_ledger'))
        assert resp.status_code == 200
        assert 'ledger' in resp.context
        assert 'accounts' in resp.context
        assert 'total_debit' in resp.context
        assert 'total_credit' in resp.context

    @pytest.mark.django_db
    def test_general_ledger_data_count(self, auth_client, journal_entry_lines):
        """عدد بنود دفتر الأستاذ العام"""
        resp = auth_client.get(reverse('reports:general_ledger'))
        assert resp.status_code == 200
        assert len(resp.context['ledger']) >= 2

    @pytest.mark.django_db
    def test_general_ledger_with_date_range(self, auth_client, sales_invoice, purchase_invoice, journal_entry_lines):
        """دفتر الأستاذ العام مع نطاق تاريخ محدد"""
        df, dt = date(2026, 1, 1), date(2026, 1, 31)
        resp = auth_client.get(reverse('reports:general_ledger'), {'date_from': df, 'date_to': dt})
        assert resp.status_code == 200
        assert resp.context['date_from'] == df
        assert resp.context['date_to'] == dt

    @pytest.mark.django_db
    def test_general_ledger_pagination(self, auth_client, journal_entry_lines):
        """دفتر الأستاذ العام مع عناصر صفحة"""
        resp = auth_client.get(reverse('reports:general_ledger'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_general_ledger_account_detail(self, auth_client, asset_account):
        """دفتر الأستاذ العام تفاصيل الحساب"""
        resp = auth_client.get(reverse('reports:general_ledger'), {'account': asset_account.id})
        assert resp.status_code == 200
        ledger = resp.context['ledger']
        for entry in ledger:
            assert entry['account_id'] == asset_account.id


# ──────────────────── 8. VAT Return View Tests ────────────────────
class TestVATReturnView:
    """اختبارات إقرار VAT"""

    def test_vat_return_requires_login(self, anon_client):
        """إقرار VAT يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:vat_return'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_vat_return_render(self, auth_client, sales_invoice, purchase_invoice):
        """عرض إقرار VAT بنجاح"""
        resp = auth_client.get(reverse('reports:vat_return'))
        assert resp.status_code == 200
        assert 'date_from' in resp.context
        assert 'date_to' in resp.context
        assert 'total_taxable_sales' in resp.context
        assert 'total_vat_output' in resp.context
        assert 'total_vat_input' in resp.context
        assert 'vat_payable' in resp.context

    @pytest.mark.django_db
    def test_vat_return_with_sample_data(self, auth_client, sales_invoice, purchase_invoice):
        """إقرار VAT مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:vat_return'))
        assert resp.status_code == 200
        assert resp.context['total_vat_output'] >= 0
        assert resp.context['total_vat_input'] >= 0

    @pytest.mark.django_db
    def test_vat_return_with_date_range(self, auth_client, sales_invoice, purchase_invoice):
        """إقرار VAT مع نطاق تاريخ محدد"""
        df, dt = date(2026, 1, 1), date(2026, 1, 31)
        resp = auth_client.get(reverse('reports:vat_return'), {'date_from': df, 'date_to': dt})
        assert resp.status_code == 200
        assert resp.context['date_from'] == df
        assert resp.context['date_to'] == dt

    @pytest.mark.django_db
    def test_vat_return_zero_values(self, auth_client):
        """إقرار VAT مع قيم صفرية"""
        resp = auth_client.get(reverse('reports:vat_return'))
        assert resp.status_code == 200
        c = resp.context
        assert 'vat_output' in c or 'total_vat_output' in c
        assert 'vat_input' in c or 'total_vat_input' in c
        assert 'vat_payable' in c

    @pytest.mark.django_db
    def test_vat_return_api_format(self, auth_client, sales_invoice, purchase_invoice):
        """إقرار VAT مع وعي بتنسيق URL وإرجاع JSON"""
        resp = auth_client.get(reverse('reports:vat_return'), {'format': 'json'})
        assert resp.status_code == 200


# ──────────────────── 9. Withholding Tax Report View Tests ────────────────────
class TestWithholdingTaxReportView:
    """اختبارات تقرير ضريبة الخصم"""

    def test_withholding_tax_requires_login(self, anon_client):
        """تقرير ضريبة الخصم يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:withholding_tax_report'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_withholding_tax_render(self, auth_client, purchase_invoice):
        """عرض تقرير ضريبة الخصم بنجاح"""
        resp = auth_client.get(reverse('reports:withholding_tax_report'))
        assert resp.status_code == 200
        assert 'date_from' in resp.context
        assert 'date_to' in resp.context
        assert 'withholding_items' in resp.context
        assert 'total_withholding' in resp.context
        assert 'total_subtotal' in resp.context

    @pytest.mark.django_db
    def test_withholding_tax_with_data(self, auth_client, purchase_invoice):
        """مع بيانات النموذجية"""
        resp = auth_client.get(reverse('reports:withholding_tax_report'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_withholding_tax_empty_data(self, auth_client):
        """مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:withholding_tax_report'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_withholding_tax_date_range(self, auth_client, purchase_invoice):
        """مع نطاق تاريخ محدد"""
        df, dt = date(2026, 1, 1), date(2026, 1, 31)
        resp = auth_client.get(reverse('reports:withholding_tax_report'), {'date_from': df, 'date_to': dt})
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_withholding_tax_rate_summary(self, auth_client, purchase_invoice):
        """مع ملخص بالمعدل"""
        resp = auth_client.get(reverse('reports:withholding_tax_report'))
        assert resp.status_code == 200
        assert 'rate_summary' in resp.context


# ──────────────────── 10. Supplier Report View Tests ────────────────────
class TestSupplierReportView:
    """اختبارات تقرير الموردين"""

    def test_supplier_report_requires_login(self, anon_client):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:supplier_report'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_supplier_report_render(self, auth_client, supplier):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:supplier_report'))
        assert resp.status_code == 200
        assert 'suppliers' in resp.context

    @pytest.mark.django_db
    def test_supplier_report_with_data(self, auth_client, supplier, purchase_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:supplier_report'))
        assert resp.status_code == 200
        assert len(resp.context['suppliers']) >= 1

    @pytest.mark.django_db
    def test_supplier_report_empty_data(self, auth_client):
        """مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:supplier_report'))
        assert resp.status_code == 200
        assert len(resp.context['suppliers']) == 0


# ──────────────────── 11. Customer Detail Report View Tests ────────────────────
class TestCustomerDetailReportView:
    """اختبارات تقرير العملاء"""

    def test_customer_detail_report_requires_login(self, anon_client, customer):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:customer_report'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_customer_detail_report_render(self, auth_client, customer):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:customer_report'))
        assert resp.status_code == 200
        assert 'customers' in resp.context

    @pytest.mark.django_db
    def test_customer_detail_report_with_data(self, auth_client, customer, sales_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:customer_report'))
        assert resp.status_code == 200
        assert len(resp.context['customers']) >= 1

    @pytest.mark.django_db
    def test_customer_detail_report_empty_data(self, auth_client):
        """مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:customer_report'))
        assert resp.status_code == 200
        assert len(resp.context['customers']) == 0


# ──────────────────── 12. Payroll Report View Tests ────────────────────
class TestPayrollReportView:
    """اختبارات تقرير الرواتب"""

    def test_payroll_report_requires_login(self, anon_client):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:payroll_report'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_payroll_report_render(self, auth_client, salary_record):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:payroll_report'))
        assert resp.status_code == 200
        assert 'year' in resp.context
        assert 'salaries' in resp.context
        assert 'total_salaries' in resp.context

    @pytest.mark.django_db
    def test_payroll_report_with_data(self, auth_client, salary_record):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:payroll_report'))
        assert resp.status_code == 200
        assert len(resp.context['salaries']) >= 1

    @pytest.mark.django_db
    def test_payroll_report_with_year_filter(self, auth_client, salary_record):
        """مع تصفية السنة"""
        resp = auth_client.get(reverse('reports:payroll_report'), {'year': 2026})
        assert resp.status_code == 200
        assert resp.context['year'] == 2026


# ──────────────────── 13. Asset Schedule View Tests ────────────────────
class TestAssetScheduleView:
    """اختبارات جدول الأصول"""

    def test_asset_schedule_requires_login(self, anon_client):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:asset_schedule'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_asset_schedule_render(self, auth_client, fixed_asset):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:asset_schedule'))
        assert resp.status_code == 200
        assert 'assets' in resp.context
        assert 'total_cost' in resp.context
        assert 'total_depreciation' in resp.context
        assert 'total_net' in resp.context

    @pytest.mark.django_db
    def test_asset_schedule_with_data(self, auth_client, fixed_asset):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:asset_schedule'))
        assert resp.status_code == 200
        assert len(resp.context['assets']) >= 1

    @pytest.mark.django_db
    def test_asset_schedule_empty_data(self, auth_client):
        """مع بيانات فارغة"""
        resp = auth_client.get(reverse('reports:asset_schedule'))
        assert resp.status_code == 200
        assert len(resp.context['assets']) == 0


# ──────────────────── 14. Cash Flow Report View Tests ────────────────────
class TestCashFlowReportView:
    """اختبارات تقرير التدفق النقدي"""

    def test_cash_flow_report_requires_login(self, anon_client):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:cash_flow_report'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_cash_flow_report_render(self, auth_client, sales_invoice, purchase_invoice):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:cash_flow_report'))
        assert resp.status_code == 200
        assert 'cash_in' in resp.context
        assert 'cash_out' in resp.context
        assert 'net_cash_flow' in resp.context

    @pytest.mark.django_db
    def test_cash_flow_report_with_data(self, auth_client, sales_invoice, purchase_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:cash_flow_report'))
        assert resp.status_code == 200
        assert 'cash_in' in resp.context
        assert 'cash_out' in resp.context
        assert 'net_cash_flow' in resp.context


# ──────────────────── 15. Budget Reports View Tests ────────────────────
class TestBudgetReportsView:
    """اختبارات تقارير الموازنة"""

    def test_budget_reports_requires_login(self, anon_client):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:budget_vs_actual'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_budget_reports_render(self, auth_client, budget_item):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:budget_vs_actual'))
        assert resp.status_code == 200
        assert 'year' in resp.context
        assert 'rows' in resp.context
        assert 'total_budgeted' in resp.context
        assert 'total_actual' in resp.context
        assert 'total_variance' in resp.context

    @pytest.mark.django_db
    def test_budget_reports_with_data(self, auth_client, budget_item):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:budget_vs_actual'))
        assert resp.status_code == 200
        assert len(resp.context['rows']) >= 1

    @pytest.mark.django_db
    def test_budget_reports_with_year_and_month(self, auth_client, budget_item):
        """مع تصفية السنة والشهر"""
        resp = auth_client.get(reverse('reports:budget_vs_actual'), {'year': 2026, 'month': 1})
        assert resp.status_code == 200
        assert resp.context['year'] == 2026
        assert resp.context['month'] == 1


# ──────────────────── 16. Inventory Reports View Tests ────────────────────
class TestInventoryReportsView:
    """اختبارات تقارير المخزون"""

    def test_inventory_reports_requires_login(self, anon_client):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:inventory_report'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_inventory_reports_render(self, auth_client, warehouse_product):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:inventory_report'))
        assert resp.status_code == 200
        assert 'warehouses' in resp.context
        assert 'warehouse_products' in resp.context
        assert 'low_stock' in resp.context
        assert 'total_stock_value' in resp.context

    @pytest.mark.django_db
    def test_inventory_reports_with_data(self, auth_client, warehouse_product):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:inventory_report'))
        assert resp.status_code == 200
        assert len(resp.context['warehouse_products']) >= 1

    @pytest.mark.django_db
    def test_inventory_reports_with_warehouse_filter(self, auth_client, warehouse_product):
        """مع تصفية المخزن"""
        resp = auth_client.get(reverse('reports:inventory_report'), {'warehouse': warehouse_product.warehouse_id})
        assert resp.status_code == 200
        assert 'selected_warehouse' in resp.context


# ──────────────────── 17. Stock Valuation Report View Tests ────────────────────
class TestStockValuationReportView:
    """اختبارات تقرير تقييم المخزون"""

    def test_stock_valuation_report_requires_login(self, anon_client):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:stock_valuation_report'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_stock_valuation_report_render(self, auth_client, warehouse_product):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:stock_valuation_report'))
        assert resp.status_code == 200
        assert 'warehouses' in resp.context
        assert 'items' in resp.context
        assert 'grand_total_value' in resp.context
        assert 'grand_total_qty' in resp.context

    @pytest.mark.django_db
    def test_stock_valuation_report_with_data(self, auth_client, warehouse_product):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:stock_valuation_report'))
        assert resp.status_code == 200
        assert 'items' in resp.context

    @pytest.mark.django_db
    def test_stock_valuation_report_with_warehouse_filter(self, auth_client, warehouse_product):
        """مع تصفية المخزن"""
        resp = auth_client.get(reverse('reports:stock_valuation_report'), {'warehouse': warehouse_product.warehouse_id})
        assert resp.status_code == 200
        assert 'selected_warehouse' in resp.context


# ──────────────────── 18. Tax Reports View Tests ────────────────────
class TestTaxReportsView:
    """اختبارات تقارير الضرائب"""

    def test_tax_reports_requires_login(self, anon_client):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:tax_summary'))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_tax_reports_render(self, auth_client, tax_invoice):
        """عرض بنجاح"""
        resp = auth_client.get(reverse('reports:tax_summary'))
        assert resp.status_code == 200
        c = resp.context
        assert 'status_rows' in c
        assert 'status_order' in c
        assert 'total_invoices' in c
        assert 'total_vat' in c

    @pytest.mark.django_db
    def test_tax_reports_with_data(self, auth_client, tax_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:tax_summary'))
        assert resp.status_code == 200
        assert len(resp.context['status_rows']) >= 1

    @pytest.mark.django_db
    def test_tax_reports_with_date_range(self, auth_client, tax_invoice):
        """مع نطاق تاريخ محدد"""
        df, dt = date(2026, 1, 1), date(2026, 1, 31)
        resp = auth_client.get(reverse('reports:tax_summary'), {'date_from': df, 'date_to': dt})
        assert resp.status_code == 200
        assert resp.context['date_from'] == df
        assert resp.context['date_to'] == dt


# ──────────────────── 19. Other Read-Only Report Views ────────────────────
class TestOtherReadOnlyReportViews:
    """اختبارات التقارير الأخرى"""

    @pytest.mark.django_db
    def test_customer_statement_render(self, auth_client, customer):
        """عرض كشف حساب العملاء"""
        resp = auth_client.get(reverse('reports:customer_statement'))
        assert resp.status_code == 200
        assert 'customers' in resp.context

    @pytest.mark.django_db
    def test_customer_statement_with_data(self, auth_client, customer, sales_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:customer_statement'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_supplier_statement_render(self, auth_client, supplier):
        """عرض كشف حساب الموردين"""
        resp = auth_client.get(reverse('reports:supplier_statement'))
        assert resp.status_code == 200
        assert 'suppliers' in resp.context

    @pytest.mark.django_db
    def test_supplier_statement_with_data(self, auth_client, supplier, purchase_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:supplier_statement'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_daily_sales_report_render(self, auth_client):
        """عرض التقرير اليومي للمبيعات"""
        resp = auth_client.get(reverse('reports:daily_sales_report'))
        assert resp.status_code == 200
        assert 'daily_list' in resp.context

    @pytest.mark.django_db
    def test_daily_sales_report_with_data(self, auth_client, sales_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:daily_sales_report'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_daily_purchases_report_render(self, auth_client):
        """عرض التقرير اليومي للمشتريات"""
        resp = auth_client.get(reverse('reports:daily_purchases_report'))
        assert resp.status_code == 200
        assert 'daily_list' in resp.context

    @pytest.mark.django_db
    def test_daily_purchases_report_with_data(self, auth_client, purchase_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:daily_purchases_report'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_ar_aging_report_render(self, auth_client):
        """عرض تقرير أعمار الذمم المدينة"""
        resp = auth_client.get(reverse('reports:ar_aging_report'))
        assert resp.status_code == 200
        assert 'aging_data' in resp.context

    @pytest.mark.django_db
    def test_ar_aging_report_with_data(self, auth_client, sales_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:ar_aging_report'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_ap_aging_report_render(self, auth_client):
        """عرض تقرير أعمار الذمم الدائنة"""
        resp = auth_client.get(reverse('reports:ap_aging_report'))
        assert resp.status_code == 200
        assert 'aging_data' in resp.context

    @pytest.mark.django_db
    def test_ap_aging_report_with_data(self, auth_client, purchase_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:ap_aging_report'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_bank_reconciliation_statement_render(self, auth_client, bank):
        """عرض كشف التسوية البنكية"""
        resp = auth_client.get(reverse('reports:bank_reconciliation_statement'))
        assert resp.status_code == 200
        assert 'banks' in resp.context

    @pytest.mark.django_db
    def test_bank_reconciliation_statement_with_data(self, auth_client, bank):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:bank_reconciliation_statement'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_payroll_detail_render(self, auth_client, salary_record):
        """عرض تقرير تفصيلي للرواتب"""
        resp = auth_client.get(reverse('reports:payroll_detail'))
        assert resp.status_code == 200
        assert 'rows' in resp.context

    @pytest.mark.django_db
    def test_payroll_detail_with_data(self, auth_client, salary_record):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:payroll_detail'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_profit_margin_report_render(self, auth_client, sales_invoice):
        """عرض تقرير نسب الربح"""
        resp = auth_client.get(reverse('reports:profit_margin_report'))
        assert resp.status_code == 200
        assert 'product_data' in resp.context

    @pytest.mark.django_db
    def test_profit_margin_report_with_data(self, auth_client, sales_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:profit_margin_report'))
        assert resp.status_code == 200


# ──────────────────── 20. Supplier Detail Report View Tests ────────────────────
class TestSupplierDetailReportView:
    """اختبارات تقرير الموردين"""

    def test_supplier_detail_report_requires_login(self, anon_client, supplier):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:supplier_detail_report', args=[supplier.id]))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_supplier_detail_report_render(self, auth_client, supplier, purchase_invoice):
        """عرض تقرير الموردين التفاصيل بنجاح"""
        resp = auth_client.get(reverse('reports:supplier_detail_report', args=[supplier.id]))
        assert resp.status_code == 200
        assert 'supplier' in resp.context
        assert 'invoices' in resp.context
        assert 'total_purchases' in resp.context
        assert 'total_paid' in resp.context

    @pytest.mark.django_db
    def test_supplier_detail_report_with_data(self, auth_client, supplier, purchase_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:supplier_detail_report', args=[supplier.id]))
        assert resp.status_code == 200


# ──────────────────── 21. Customer Detail Report View Tests (again) ────────────────────
class TestCustomerDetailReportView2:
    """اختبارات تقرير العملاء"""

    def test_customer_detail_report_requires_login(self, anon_client, customer):
        """يتطلب تسجيل دخول"""
        resp = anon_client.get(reverse('reports:customer_detail_report', args=[customer.id]))
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_customer_detail_report_render(self, auth_client, customer, sales_invoice):
        """عرض تقرير العملاء التفاصيل بنجاح"""
        resp = auth_client.get(reverse('reports:customer_detail_report', args=[customer.id]))
        assert resp.status_code == 200
        assert 'customer' in resp.context
        assert 'invoices' in resp.context
        assert 'total_sales' in resp.context
        assert 'total_collected' in resp.context

    @pytest.mark.django_db
    def test_customer_detail_report_with_data(self, auth_client, customer, sales_invoice):
        """مع بيانات نموذجية"""
        resp = auth_client.get(reverse('reports:customer_detail_report', args=[customer.id]))
        assert resp.status_code == 200


# ──────────────────── 22. Export Report View Tests ────────────────────
class TestExportReportView:
    """اختبارات تصدير التقارير"""

    def test_export_unknown_type(self, auth_client, date_range):
        """تصدير تقرير غير معروف"""
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['unknown-type']),
            {'date_from': df, 'date_to': dt},
        )
        assert resp.status_code == 404

    def test_export_requires_login(self, anon_client):
        """التصدير يتطلب تسجيل دخول"""
        resp = anon_client.get(
            reverse('reports:export_report', args=['daily-sales']),
        )
        assert resp.status_code == 302

    @patch('reports.views.export_to_excel')
    def test_export_daily_sales_xlsx(self, mock_export, auth_client, sales_invoice, date_range):
        """تصدير يومية المبيعات كملف Excel"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['daily-sales']),
            {'date_from': df, 'date_to': dt, 'format': 'excel'},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_daily_purchases_xlsx(self, mock_export, auth_client, purchase_invoice, date_range):
        """تصدير يومية المشتريات كملف Excel"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['daily-purchases']),
            {'date_from': df, 'date_to': dt, 'format': 'excel'},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_ar_aging(self, mock_export, auth_client, sales_invoice, date_range):
        """تصدير تقرير أعمار الذمم المدينة"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['ar-aging']),
            {'date_from': df, 'date_to': dt},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_ap_aging(self, mock_export, auth_client, purchase_invoice, date_range):
        """تصدير تقرير أعمار الذمم الدائنة"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['ap-aging']),
            {'date_from': df, 'date_to': dt},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_income_statement(self, mock_export, auth_client, date_range):
        """تصدير قائمة الدخل"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['income-statement']),
            {'date_from': df, 'date_to': dt},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_vat_return(self, mock_export, auth_client, date_range):
        """تصدير إقرار VAT"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['vat-return']),
            {'date_from': df, 'date_to': dt},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_inventory(self, mock_export, auth_client, date_range):
        """تصدير تقرير المخزون"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['inventory']),
            {'date_from': df, 'date_to': dt},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_profit_margin(self, mock_export, auth_client, date_range):
        """تصدير تقرير نسب الربح"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['profit-margin']),
            {'date_from': df, 'date_to': dt},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_pdf')
    def test_export_daily_sales_pdf(self, mock_pdf, auth_client, sales_invoice, date_range):
        """تصدير يومية المبيعات كـ PDF"""
        mock_pdf.return_value = HttpResponse(b'%PDF-fake', content_type='application/pdf')
        df, dt = date_range
        resp = auth_client.get(
            reverse('reports:export_report', args=['daily-sales']),
            {'date_from': df, 'date_to': dt, 'format': 'pdf'},
        )
        assert resp.status_code == 200
        mock_pdf.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_with_default_dates(self, mock_export, auth_client):
        """التصدير مع التواريخ الافتراضية"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        resp = auth_client.get(
            reverse('reports:export_report', args=['daily-sales']),
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_with_reversed_dates(self, mock_export, auth_client):
        """التصدير مع تواريخ معكوسة"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        resp = auth_client.get(
            reverse('reports:export_report', args=['daily-sales']),
            {'date_from': '2026-12-31', 'date_to': '2026-01-01'},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()

    @patch('reports.views.export_to_excel')
    def test_export_with_invalid_date(self, mock_export, auth_client):
        """التصدير مع تاريخ غير صالح"""
        mock_export.return_value = HttpResponse(b'fake', content_type='application/octet-stream')
        resp = auth_client.get(
            reverse('reports:export_report', args=['daily-sales']),
            {'date_from': 'not-a-date', 'date_to': 'also-bad'},
        )
        assert resp.status_code == 200
        mock_export.assert_called_once()


# ──────────────────── 23. Helper Functions Tests ────────────────────
class TestHelperFunctions:
    """اختبارات الدوال المساعدة"""

    def test_safe_parse_date_valid(self):
        """تحليل تاريخ صالح"""
        from reports.views import _safe_parse_date

        result = _safe_parse_date('2026-06-15', 'test')
        assert result == date(2026, 6, 15)

    def test_safe_parse_date_invalid(self):
        """تحليل تاريخ غير صالح"""
        from reports.views import _safe_parse_date

        result = _safe_parse_date('invalid-date', 'test')
        assert result is None

    def test_safe_parse_date_none(self):
        """تحليل تاريخ None"""
        from reports.views import _safe_parse_date

        assert _safe_parse_date(None) is None
        assert _safe_parse_date('') == ''

    def test_validate_date_range_swapped(self):
        """التحقق من تبادل تواريخ معكوسة"""
        from unittest.mock import MagicMock

        from reports.views import _validate_date_range

        request = MagicMock()
        request.GET = {}
        request.session = {}
        request._messages = MagicMock()
        df, dt = _validate_date_range(request, date(2026, 12, 31), date(2026, 1, 1))
        assert df == date(2026, 1, 1)

    def test_get_date_range_defaults(self):
        """جلب نطاق التاريخ مع التواريخ الافتراضية"""

        from reports.views import _get_date_range

        factory = RequestFactory()
        request = factory.get('/test/')
        df, dt = _get_date_range(request)
        assert df is not None
        assert dt is not None

    def test_get_date_range_with_valid_dates(self):
        """جلب نطاق التاريخ مع تواريخ صالحة"""

        from reports.views import _get_date_range

        factory = RequestFactory()
        request = factory.get('/test/', {'date_from': '2026-01-01', 'date_to': '2026-12-31'})
        df, dt = _get_date_range(request)
        assert df == date(2026, 1, 1)
        assert dt == date(2026, 12, 31)

    def test_get_date_range_with_invalid_date(self):
        """جلب نطاق التاريخ مع تاريخ غير صالح"""
        from unittest.mock import MagicMock

        from reports.views import _get_date_range

        request = MagicMock()
        request.GET = {'date_from': 'invalid', 'date_to': 'also-bad'}
        request.session = {}
        request._messages = MagicMock()
        df, dt = _get_date_range(request)
        assert df is not None
        assert dt is not None

    def test_posted_lines_in_range(self):
        """اختبار تجميع خطوط القيود المرحلة"""
        from reports.views import _posted_lines_in_range

        result = _posted_lines_in_range(None, None)
        assert isinstance(result, dict)

    def test_period_net(self):
        """اختبار صافي النشاط الدفتري"""
        from reports.views import _period_net

        activity = {'debit': Decimal('100'), 'credit': Decimal('50')}
        net = _period_net(activity, 'asset')
        assert net > 0
        net = _period_net(activity, 'liability')
        assert net == Decimal('-50')

    def test_trial_balance_split(self):
        """اختبار تقسيم ميزان المراجعة"""
        from reports.views import _trial_balance_split

        debit, credit = _trial_balance_split(Decimal('100'), 'asset')
        assert debit == Decimal('100') and credit == Decimal('0')
        debit, credit = _trial_balance_split(Decimal('100'), 'liability')
        assert debit == Decimal('0') and credit == Decimal('100')

    def test_balances_as_of(self):
        """اختبار أرصدة الحسابات حتى تاريخ معين"""
        from reports.views import _balances_as_of

        result = _balances_as_of([], date(2026, 1, 1))
        assert isinstance(result, dict)
