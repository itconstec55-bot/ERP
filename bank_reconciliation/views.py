from django.contrib.auth.decorators import login_required
from common.permissions import screen_permission_required
from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import models, transaction
from django.http import HttpResponse
from .models import BankStatementItem, ReconciliationSession
from .forms import ReconciliationSessionForm, BankStatementItemForm
from treasury.models import Bank
import csv
import io
from decimal import Decimal, InvalidOperation


@screen_permission_required('bank_reconciliation.statement', 'view')
@cache_page(120)
@vary_on_cookie
def reconciliation_dashboard(request):
    sessions = ReconciliationSession.objects.select_related('bank_account', 'created_by').all()[:20]
    unmatched_count = BankStatementItem.objects.filter(status='unmatched').count()
    matched_count = BankStatementItem.objects.filter(status='matched').count()
    total_items = BankStatementItem.objects.count()
    banks = Bank.objects.filter(is_active=True)
    bank_balances = {}
    bank_items = BankStatementItem.objects.values('bank_account').annotate(
        total_credit=models.Sum('credit_amount'),
        total_debit=models.Sum('debit_amount'),
        count=models.Count('id'),
    )
    bank_lookup = {bank.pk: bank for bank in banks}
    for item in bank_items:
        bid = item['bank_account']
        if bid in bank_lookup:
            bank_balances[bid] = {
                'bank': bank_lookup[bid],
                'total_credit': item['total_credit'] or 0,
                'total_debit': item['total_debit'] or 0,
                'count': item['count'],
            }
    return render(request, 'bank_reconciliation/dashboard.html', {
        'sessions': sessions, 'unmatched_count': unmatched_count,
        'matched_count': matched_count, 'total_items': total_items,
        'bank_balances': bank_balances.values(),
    })


@screen_permission_required('bank_reconciliation.statement', 'add')
def session_create(request):
    banks = Bank.objects.filter(is_active=True)
    if request.method == 'POST':
        form = ReconciliationSessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.created_by = request.user
            session.save()
            session.calculate_difference()
            messages.success(request, 'تم إنشاء جلسة التسوية')
            return redirect('bank_reconciliation:session_detail', pk=session.pk)
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f'{form.fields[field].label if field in form.fields else field}: {err}')
        return render(request, 'bank_reconciliation/session_form.html', {'banks': banks, 'form': form})
    return render(request, 'bank_reconciliation/session_form.html', {'banks': banks, 'form': ReconciliationSessionForm()})


@screen_permission_required('bank_reconciliation.statement', 'view')
def session_detail(request, pk):
    session = get_object_or_404(ReconciliationSession, pk=pk)
    items = BankStatementItem.objects.filter(bank_account=session.bank_account, transaction_date__range=[session.period_start, session.period_end])
    return render(request, 'bank_reconciliation/session_detail.html', {'session': session, 'items': items})


@screen_permission_required('bank_reconciliation.statement', 'view')
def item_list(request):
    items = BankStatementItem.objects.select_related('bank_account').all()
    bank_id = request.GET.get('bank')
    status = request.GET.get('status')
    if bank_id:
        items = items.filter(bank_account_id=bank_id)
    if status:
        items = items.filter(status=status)
    banks = Bank.objects.filter(is_active=True)
    return render(request, 'bank_reconciliation/item_list.html', {'items': items, 'banks': banks})


@screen_permission_required('bank_reconciliation.statement', 'add')
def item_create(request):
    banks = Bank.objects.filter(is_active=True)
    if request.method == 'POST':
        form = BankStatementItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة البند')
            return redirect('bank_reconciliation:item_list')
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f'{form.fields[field].label if field in form.fields else field}: {err}')
        return render(request, 'bank_reconciliation/item_form.html', {'banks': banks, 'form': form})
    return render(request, 'bank_reconciliation/item_form.html', {'banks': banks, 'form': BankStatementItemForm()})


@screen_permission_required('bank_reconciliation.statement', 'edit')
def item_match(request, pk):
    item = get_object_or_404(BankStatementItem, pk=pk)
    if request.method == 'POST':
        from treasury.models import BankTransaction
        tx_id = request.POST.get('transaction_id')
        if tx_id:
            tx = BankTransaction.objects.filter(pk=tx_id, bank_id=item.bank_account_id).first()
            if tx:
                item.matched_transaction = tx
                item.status = 'matched'
                item.save()
                messages.success(request, 'تم مطابقة البند')
            else:
                messages.error(request, 'المعاملة المحددة غير موجودة أو لا تخص نفس الحساب البنكي')
    return redirect('bank_reconciliation:item_list')


@screen_permission_required('bank_reconciliation.statement', 'add')
def import_csv(request):
    banks = Bank.objects.filter(is_active=True)
    if request.method != 'POST':
        return render(request, 'bank_reconciliation/import_csv.html', {'banks': banks})

    bank_id = request.POST.get('bank_account')
    file = request.FILES.get('csv_file')
    if not bank_id or not file:
        messages.error(request, 'يرجى اختيار البنك ورفع ملف CSV أو Excel')
        return redirect('bank_reconciliation:import_csv')

    bank = get_object_or_404(Bank, pk=bank_id)
    filename = file.name.lower()

    try:
        if filename.endswith(('.xlsx', '.xls')):
            rows = _parse_excel_import(file)
        else:
            rows = _parse_csv_import(file)
    except Exception:
        messages.error(request, 'خطأ في قراءة الملف، يرجى التحقق من صيغة البيانات')
        return redirect('bank_reconciliation:import_csv')

    created = 0
    skipped = 0
    duplicates = 0

    with transaction.atomic():
        for row in rows:
            try:
                date_val = row.get('date') or row.get('التاريخ') or row.get('Date') or ''
                desc = row.get('description') or row.get('الوصف') or row.get('Description') or row.get('البيان', '')
                ref = row.get('reference') or row.get('المرجع') or row.get('Reference') or ''
                debit_str = row.get('debit') or row.get('المدين') or row.get('Debit') or row.get('debit_amount', '0')
                credit_str = row.get('credit') or row.get('الدائن') or row.get('Credit') or row.get('credit_amount', '0')

                if not date_val or not desc:
                    skipped += 1
                    continue

                from decimal import Decimal, InvalidOperation
                debit_val = Decimal(str(debit_str).replace(',', '').replace('"', '').strip() or '0')
                credit_val = Decimal(str(credit_str).replace(',', '').replace('"', '').strip() or '0')
                if debit_val < 0 or credit_val < 0:
                    skipped += 1
                    continue

                from datetime import datetime as dt
                date_obj = None
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
                    try:
                        date_obj = dt.strptime(date_val.strip(), fmt).date()
                        break
                    except ValueError:
                        continue
                if not date_obj:
                    skipped += 1
                    continue

                amount_val = credit_val - debit_val if credit_val > 0 else debit_val

                exists = BankStatementItem.objects.filter(
                    bank_account=bank,
                    transaction_date=date_obj,
                    description=desc.strip(),
                    debit_amount=debit_val,
                    credit_amount=credit_val,
                ).exists()
                if exists:
                    duplicates += 1
                    continue

                BankStatementItem.objects.create(
                    bank_account=bank,
                    transaction_date=date_obj,
                    description=desc.strip(),
                    reference=ref.strip(),
                    debit_amount=debit_val,
                    credit_amount=credit_val,
                )
                created += 1
            except (InvalidOperation, ValueError, KeyError):
                skipped += 1
                continue

    if created > 0:
        messages.success(request, f'تم استيراد {created} بند بنجاح')
    if duplicates > 0:
        messages.info(request, f'تم تخطي {duplicates} بند مكرر')
    if skipped > 0:
        messages.warning(request, f'تم تخطي {skipped} سطر بسبب أخطاء في البيانات')
    return redirect('bank_reconciliation:item_list')


def _parse_csv_import(file):
    import csv, io
    decoded = file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(decoded))
    return list(reader)


def _parse_excel_import(file):
    try:
        import openpyxl
    except ImportError:
        raise ValueError('openpyxl is required for Excel import')
    
    wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h or '').strip() for h in rows[0]]
    result = []
    for row in rows[1:]:
        row_dict = {}
        for i, val in enumerate(row):
            if i < len(headers) and headers[i]:
                row_dict[headers[i]] = str(val) if val is not None else ''
        result.append(row_dict)
    return result


@screen_permission_required('bank_reconciliation.statement', 'edit')
def auto_match(request):
    if request.method != 'POST':
        return redirect('bank_reconciliation:item_list')

    bank_id = request.POST.get('bank_account')
    unmatched = BankStatementItem.objects.filter(status='unmatched')
    if bank_id:
        unmatched = unmatched.filter(bank_account_id=bank_id)

    matched_count = 0
    with transaction.atomic():
        from treasury.models import BankTransaction
        unmatched = list(unmatched)
        if not unmatched:
            return redirect('bank_reconciliation:item_list')

        bank_ids = {item.bank_account_id for item in unmatched}
        dates = {item.transaction_date for item in unmatched}
        amounts = {abs(item.amount) for item in unmatched}

        tx_candidates = BankTransaction.objects.filter(
            bank_id__in=bank_ids,
            transaction_date__in=dates,
            amount__in=amounts,
        ).select_for_update()

        tx_map = {}
        for tx in tx_candidates:
            key = (tx.bank_id, tx.transaction_date, tx.amount)
            tx_map.setdefault(key, []).append(tx)

        for item in unmatched:
            key = (item.bank_account_id, item.transaction_date, abs(item.amount))
            candidates = tx_map.get(key, [])
            matched_tx = None
            for tx in candidates:
                if tx.id != (item.matched_transaction_id or None):
                    matched_tx = tx
                    break
            if matched_tx:
                item.matched_transaction = matched_tx
                item.status = 'matched'
                item.save(update_fields=['matched_transaction', 'status'])
                matched_count += 1

    if matched_count > 0:
        messages.success(request, f'تم مطابقة {matched_count} بند تلقائياً')
    else:
        messages.info(request, 'لم يتم العثور على بنود للمطابقة التلقائية')

    return redirect('bank_reconciliation:item_list')


@screen_permission_required('bank_reconciliation.statement', 'delete')
@require_POST
def item_delete(request, pk):
    item = get_object_or_404(BankStatementItem, pk=pk)
    item.delete()
    messages.success(request, 'تم حذف البند')
    return redirect('bank_reconciliation:item_list')


@screen_permission_required('bank_reconciliation.statement', 'edit')
@require_POST
def item_unmatch(request, pk):
    """إلغاء مطابقة بند."""
    item = get_object_or_404(BankStatementItem, pk=pk)
    item.matched_transaction = None
    item.status = 'unmatched'
    item.save(update_fields=['matched_transaction', 'status'])
    messages.success(request, 'تم إلغاء مطابقة البند')
    return redirect('bank_reconciliation:item_list')
