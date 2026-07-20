from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import CreditNote
from sales.models import Customer, SalesInvoice
from purchases.models import Supplier, PurchaseInvoice
from common.permissions import screen_permission_required


@screen_permission_required('credit_notes.creditnote', 'view')
def credit_note_list(request):
    notes = CreditNote.objects.select_related(
        'customer', 'supplier', 'original_sales_invoice', 'original_purchase_invoice'
    ).all()
    note_type = request.GET.get('type')
    if note_type:
        notes = notes.filter(note_type=note_type)
    return render(request, 'credit_notes/credit_note_list.html', {'notes': notes})


@screen_permission_required('credit_notes.creditnote', 'add')
def credit_note_create(request):
    customers = Customer.objects.all()
    suppliers = Supplier.objects.all()
    sales_invoices = SalesInvoice.objects.all().order_by('-date')
    purchase_invoices = PurchaseInvoice.objects.all().order_by('-date')
    if request.method == 'POST':
        from django.db import transaction
        from decimal import Decimal, InvalidOperation
        errors = []
        note_type = request.POST.get('note_type', 'credit_note').strip()
        note_number = request.POST.get('note_number', '').strip()
        date_val = request.POST.get('date', '').strip()
        if not note_number:
            errors.append('رقم الإشعار مطلوب.')
        if not date_val:
            errors.append('تاريخ الإشعار مطلوب.')
        if note_type not in ('credit_note', 'debit_note'):
            errors.append('نوع الإشعار غير صالح.')

        try:
            subtotal = Decimal(request.POST.get('subtotal', '0') or '0')
        except (InvalidOperation, ValueError):
            subtotal = None
            errors.append('المجموع الفرعي غير صالح.')
        try:
            vat = Decimal(request.POST.get('vat_amount', '0') or '0')
        except (InvalidOperation, ValueError):
            vat = None
            errors.append('قيمة الضريبة غير صالحة.')
        if subtotal is not None and subtotal < 0:
            errors.append('المجموع الفرعي لا يمكن أن يكون سالباً.')
        if vat is not None and vat < 0:
            errors.append('قيمة الضريبة لا يمكن أن تكون سالبة.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'credit_notes/credit_note_form.html', {
                'customers': customers, 'suppliers': suppliers,
                'sales_invoices': sales_invoices, 'purchase_invoices': purchase_invoices,
            })

        sales_invoice_id = request.POST.get('original_sales_invoice') or None
        purchase_invoice_id = request.POST.get('original_purchase_invoice') or None

        with transaction.atomic():
            cn = CreditNote.objects.create(
                note_type=note_type,
                note_number=note_number,
                date=date_val,
                customer_id=request.POST.get('customer') or None,
                supplier_id=request.POST.get('supplier') or None,
                original_invoice_number=request.POST.get('original_invoice_number', ''),
                original_sales_invoice_id=sales_invoice_id,
                original_purchase_invoice_id=purchase_invoice_id,
                subtotal=subtotal,
                vat_amount=vat,
                total_amount=subtotal + vat,
                reason=request.POST.get('reason', ''),
                notes=request.POST.get('notes', ''),
            )
        messages.success(request, f'تم إنشاء {cn.get_note_type_display()} بنجاح')
        return redirect('credit_notes:credit_note_list')
    return render(request, 'credit_notes/credit_note_form.html', {
        'customers': customers, 'suppliers': suppliers,
        'sales_invoices': sales_invoices, 'purchase_invoices': purchase_invoices,
    })


@screen_permission_required('credit_notes.creditnote', 'view')
def credit_note_detail(request, pk):
    note = get_object_or_404(CreditNote, pk=pk)
    return render(request, 'credit_notes/credit_note_detail.html', {'note': note})


@require_POST
@screen_permission_required('credit_notes.creditnote', 'edit')
def credit_note_post(request, pk):
    note = get_object_or_404(CreditNote, pk=pk)
    if note.is_posted:
        messages.warning(request, 'تم ترحيل هذا الإشعار مسبقاً')
        return redirect('credit_notes:credit_note_list')
    from django.db import transaction as db_transaction
    from common.accounting_service import JournalEntryService
    if note.note_type == 'credit_note':
        if note.customer:
            lines = [
                {'account': note.customer.account or JournalEntryService.get_account('1100'),
                 'debit': note.total_amount, 'credit': 0, 'description': note.note_number},
                {'account': JournalEntryService.get_account('6100'), 'debit': 0, 'credit': note.subtotal,
                 'description': note.note_number},
            ]
            if note.vat_amount > 0:
                lines.append({'account': JournalEntryService.get_account('3200'), 'debit': 0,
                              'credit': note.vat_amount, 'description': note.note_number})
        else:
            lines = [
                {'account': JournalEntryService.get_account('6100'), 'debit': note.subtotal, 'credit': 0,
                 'description': note.note_number},
                {'account': JournalEntryService.get_account('3200'), 'debit': note.vat_amount, 'credit': 0,
                 'description': note.note_number},
                {'account': JournalEntryService.get_account('1100'), 'debit': 0, 'credit': note.total_amount,
                 'description': note.note_number},
            ]
    else:
        if note.supplier:
            lines = [
                {'account': note.supplier.account or JournalEntryService.get_account('3100'),
                 'debit': 0, 'credit': note.total_amount, 'description': note.note_number},
                {'account': JournalEntryService.get_account('1300'), 'debit': note.subtotal, 'credit': 0,
                 'description': note.note_number},
            ]
            if note.vat_amount > 0:
                lines.append({'account': JournalEntryService.get_account('1350'), 'debit': note.vat_amount,
                              'credit': 0, 'description': note.note_number})
        else:
            lines = [
                {'account': JournalEntryService.get_account('1300'), 'debit': note.subtotal, 'credit': 0,
                 'description': note.note_number},
                {'account': JournalEntryService.get_account('1350'), 'debit': note.vat_amount, 'credit': 0,
                 'description': note.note_number},
                {'account': JournalEntryService.get_account('3100'), 'debit': 0, 'credit': note.total_amount,
                 'description': note.note_number},
            ]
    with db_transaction.atomic():
        entry = JournalEntryService.create_entry(
            entry_type='general', date=note.date,
            description=note.reason,
            reference=f'CN-{note.note_number}',
            lines=lines,
            created_by=request.user,
        )
        note.journal_entry = entry
        note.is_posted = True
        note.save(update_fields=['journal_entry', 'is_posted'])
    messages.success(request, f'تم ترحيل {note.get_note_type_display()} - قيد رقم {entry.entry_number}')
    return redirect('credit_notes:credit_note_list')


@require_POST
@screen_permission_required('credit_notes.creditnote', 'delete')
def credit_note_delete(request, pk):
    note = get_object_or_404(CreditNote, pk=pk)
    if note.is_posted:
        messages.error(request, 'لا يمكن حذف إشعار تم ترحيله')
    else:
        note.delete()
        messages.success(request, 'تم الحذف')
    return redirect('credit_notes:credit_note_list')
