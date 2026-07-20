from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from common.permissions import screen_permission_required
from common.excel_utils import export_to_excel, import_from_excel
from common.exceptions import AccountingError
from .models import Bank, Safe, BankTransaction, SafeTransaction
from .forms import BankForm, SafeForm, BankTransactionForm, SafeTransactionForm
import logging

logger = logging.getLogger('accounting')


@screen_permission_required('treasury.bank', 'view')
def bank_list(request):
    banks = Bank.objects.filter(is_active=True)
    return render(request, 'treasury/bank_list.html', {'banks': banks})


@screen_permission_required('treasury.bank', 'add')
def bank_create(request):
    if request.method == 'POST':
        form = BankForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة البنك بنجاح')
            return redirect('treasury:bank_list')
    else:
        form = BankForm()
    return render(request, 'treasury/bank_form.html', {'form': form})


@screen_permission_required('treasury.bank', 'view')
def bank_detail(request, pk):
    bank = get_object_or_404(Bank, pk=pk)
    transactions = BankTransaction.objects.filter(bank=bank).select_related('journal_entry', 'created_by').order_by('-date')[:50]
    return render(request, 'treasury/bank_detail.html', {
        'bank': bank,
        'transactions': transactions,
    })


@screen_permission_required('treasury.bank', 'edit')
def bank_edit(request, pk):
    bank = get_object_or_404(Bank, pk=pk)
    if request.method == 'POST':
        form = BankForm(request.POST, instance=bank)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل البنك بنجاح')
            return redirect('treasury:bank_detail', pk=pk)
    else:
        form = BankForm(instance=bank)
    return render(request, 'treasury/bank_form.html', {'form': form, 'bank': bank})


@require_POST
@screen_permission_required('treasury.bank', 'delete')
def bank_delete(request, pk):
    bank = get_object_or_404(Bank, pk=pk)
    if BankTransaction.objects.filter(bank=bank).exists():
        messages.error(request, 'لا يمكن حذف بنك يحتوي على معاملات')
    else:
        bank.delete()
        messages.success(request, 'تم حذف البنك بنجاح')
    return redirect('treasury:bank_list')


@screen_permission_required('treasury.bank', 'add')
def bank_transaction_create(request, bank_id):
    bank = get_object_or_404(Bank, pk=bank_id)
    if request.method == 'POST':
        form = BankTransactionForm(request.POST)
        if form.is_valid():
            bank_tx = form.save(commit=False)
            bank_tx.bank = bank
            bank_tx.created_by = request.user
            try:
                bank_tx.save()
                messages.success(request, 'تم إضافة المعاملة بنجاح')
                return redirect('treasury:bank_detail', pk=bank_id)
            except AccountingError as e:
                messages.error(request, str(e))
                logger.warning('Bank transaction failed: %s', e)
    else:
        form = BankTransactionForm()
    return render(request, 'treasury/transaction_form.html', {
        'form': form,
        'bank': bank,
        'title': 'معاملة بنكية',
    })


@screen_permission_required('treasury.safe', 'view')
def safe_list(request):
    safes = Safe.objects.filter(is_active=True)
    return render(request, 'treasury/safe_list.html', {'safes': safes})


@screen_permission_required('treasury.safe', 'add')
def safe_create(request):
    if request.method == 'POST':
        form = SafeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الخزينة بنجاح')
            return redirect('treasury:safe_list')
    else:
        form = SafeForm()
    return render(request, 'treasury/safe_form.html', {'form': form})


@screen_permission_required('treasury.safe', 'view')
def safe_detail(request, pk):
    safe = get_object_or_404(Safe, pk=pk)
    transactions = SafeTransaction.objects.filter(safe=safe).select_related('journal_entry', 'created_by').order_by('-date')[:50]
    return render(request, 'treasury/safe_detail.html', {
        'safe': safe,
        'transactions': transactions,
    })


@screen_permission_required('treasury.safe', 'edit')
def safe_edit(request, pk):
    safe = get_object_or_404(Safe, pk=pk)
    if request.method == 'POST':
        form = SafeForm(request.POST, instance=safe)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل الخزينة بنجاح')
            return redirect('treasury:safe_detail', pk=pk)
    else:
        form = SafeForm(instance=safe)
    return render(request, 'treasury/safe_form.html', {'form': form, 'safe': safe})


@require_POST
@screen_permission_required('treasury.safe', 'delete')
def safe_delete(request, pk):
    safe = get_object_or_404(Safe, pk=pk)
    if SafeTransaction.objects.filter(safe=safe).exists():
        messages.error(request, 'لا يمكن حذف خزينة تحتوي على معاملات')
    else:
        safe.delete()
        messages.success(request, 'تم حذف الخزينة بنجاح')
    return redirect('treasury:safe_list')


@screen_permission_required('treasury.safe', 'add')
def safe_transaction_create(request, safe_id):
    safe = get_object_or_404(Safe, pk=safe_id)
    if request.method == 'POST':
        form = SafeTransactionForm(request.POST)
        if form.is_valid():
            safe_tx = form.save(commit=False)
            safe_tx.safe = safe
            safe_tx.created_by = request.user
            try:
                safe_tx.save()
                messages.success(request, 'تم إضافة المعاملة بنجاح')
                return redirect('treasury:safe_detail', pk=safe_id)
            except AccountingError as e:
                messages.error(request, str(e))
                logger.warning('Safe transaction failed: %s', e)
    else:
        form = SafeTransactionForm()
    return render(request, 'treasury/transaction_form.html', {
        'form': form,
        'safe': safe,
        'title': 'معاملة خزينة',
    })


@screen_permission_required('treasury.bank', 'export')
def export_banks(request):
    banks = Bank.objects.all()
    return export_to_excel(banks, [
        {'field': 'name', 'header': 'اسم البنك', 'width': 25},
        {'field': 'branch', 'header': 'الفرع', 'width': 20},
        {'field': 'account_number', 'header': 'رقم الحساب', 'width': 20},
        {'field': 'current_balance', 'header': 'الرصيد الحالي', 'width': 18},
    ], filename="banks")


@screen_permission_required('treasury.safe', 'export')
def export_safes(request):
    safes = Safe.objects.all()
    return export_to_excel(safes, [
        {'field': 'name', 'header': 'اسم الخزينة', 'width': 25},
        {'field': 'responsible_person', 'header': 'المسؤول', 'width': 20},
        {'field': 'current_balance', 'header': 'الرصيد الحالي', 'width': 18},
        {'field': 'maximum_limit', 'header': 'الحد الأقصى', 'width': 18},
    ], filename="safes")


@screen_permission_required('treasury.bank', 'add')
def import_banks(request):
    if request.method != 'POST':
        return redirect('treasury:bank_list')
    file = request.FILES.get('excel_file')
    if not file:
        messages.error(request, 'يرجى اختيار ملف Excel')
        return redirect('treasury:bank_list')
    try:
        rows = import_from_excel(file, [
            {'field': 'name', 'header': 'اسم البنك'},
            {'field': 'branch', 'header': 'الفرع'},
            {'field': 'account_number', 'header': 'رقم الحساب'},
            {'field': 'current_balance', 'header': 'الرصيد الحالي', 'type': 'decimal'},
        ])
        created = 0
        for row in rows:
            Bank.objects.create(
                name=row.get('name', ''),
                branch=row.get('branch', ''),
                account_number=row.get('account_number', ''),
                current_balance=row.get('current_balance', 0),
            )
            created += 1
        messages.success(request, f'تم استيراد {created} بنك بنجاح')
    except Exception as e:
        messages.error(request, 'حدث خطأ أثناء الاستيراد. تأكد من صحة بيانات الملف وحاول مرة أخرى.')
        logger.exception('Import failed')
    return redirect('treasury:bank_list')


@screen_permission_required('treasury.safe', 'add')
def import_safes(request):
    if request.method != 'POST':
        return redirect('treasury:safe_list')
    file = request.FILES.get('excel_file')
    if not file:
        messages.error(request, 'يرجى اختيار ملف Excel')
        return redirect('treasury:safe_list')
    try:
        rows = import_from_excel(file, [
            {'field': 'name', 'header': 'اسم الخزينة'},
            {'field': 'responsible_person', 'header': 'المسؤول'},
            {'field': 'current_balance', 'header': 'الرصيد الحالي', 'type': 'decimal'},
            {'field': 'maximum_limit', 'header': 'الحد الأقصى', 'type': 'decimal'},
        ])
        created = 0
        for row in rows:
            Safe.objects.create(
                name=row.get('name', ''),
                responsible_person=row.get('responsible_person', ''),
                current_balance=row.get('current_balance', 0),
                maximum_limit=row.get('maximum_limit', 0),
            )
            created += 1
        messages.success(request, f'تم استيراد {created} خزينة بنجاح')
    except Exception as e:
        messages.error(request, 'حدث خطأ أثناء الاستيراد. تأكد من صحة بيانات الملف وحاول مرة أخرى.')
        logger.exception('Import failed')
    return redirect('treasury:safe_list')
