import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.permissions import screen_permission_required
from purchases.models import PurchaseInvoice, Supplier
from sales.models import Customer, SalesInvoice
from treasury.models import Bank, Safe

from .forms import PaymentReceiptForm
from .models import PaymentReceipt

logger = logging.getLogger('accounting')


@screen_permission_required('payment_receipts.paymentreceipt', 'view')
def receipt_list(request):
    receipts = PaymentReceipt.objects.select_related('customer', 'supplier', 'bank', 'safe').all()

    rtype = request.GET.get('type')
    status = request.GET.get('status')
    method = request.GET.get('method')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if rtype:
        receipts = receipts.filter(receipt_type=rtype)
    if status == 'posted':
        receipts = receipts.filter(is_posted=True)
    elif status == 'draft':
        receipts = receipts.filter(is_posted=False)
    if method:
        receipts = receipts.filter(payment_method=method)
    if date_from:
        receipts = receipts.filter(date__gte=date_from)
    if date_to:
        receipts = receipts.filter(date__lte=date_to)

    all_receipts = PaymentReceipt.objects.all()
    total_receipts = all_receipts.filter(receipt_type='receipt').count()
    total_payments = all_receipts.filter(receipt_type='payment').count()
    total_receipt_amount = all_receipts.filter(receipt_type='receipt').aggregate(s=Sum('amount'))['s'] or 0
    total_payment_amount = all_receipts.filter(receipt_type='payment').aggregate(s=Sum('amount'))['s'] or 0
    total_count = all_receipts.count()
    unposted_count = all_receipts.filter(is_posted=False).count()

    paginator_obj = Paginator(receipts, 25)
    page = request.GET.get('page')
    receipts_page = paginator_obj.get_page(page)
    return render(
        request,
        'payment_receipts/receipt_list.html',
        {
            'receipts': receipts_page,
            'total_receipts': total_receipts,
            'total_payments': total_payments,
            'total_receipt_amount': total_receipt_amount,
            'total_payment_amount': total_payment_amount,
            'total_count': total_count,
            'unposted_count': unposted_count,
        },
    )


@screen_permission_required('payment_receipts.paymentreceipt', 'add')
def receipt_create(request):
    receipt_type = request.GET.get('type', 'receipt')
    customers = Customer.objects.filter(is_active=True)
    suppliers = Supplier.objects.filter(is_active=True)
    banks = Bank.objects.filter(is_active=True)
    safes = Safe.objects.filter(is_active=True)

    if request.method == 'POST':
        form = PaymentReceiptForm(request.POST)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.created_by = request.user
            receipt.save()
            messages.success(request, f'تم إنشاء السند {receipt.receipt_number} بنجاح')
            return redirect('payment_receipts:detail', pk=receipt.pk)
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f'{form.fields[field].label if field in form.fields else field}: {err}')
            customers = Customer.objects.filter(is_active=True)
            suppliers = Supplier.objects.filter(is_active=True)
            banks = Bank.objects.filter(is_active=True)
            safes = Safe.objects.filter(is_active=True)
            return render(
                request,
                'payment_receipts/receipt_form.html',
                {
                    'customers': customers,
                    'suppliers': suppliers,
                    'banks': banks,
                    'safes': safes,
                    'next_number': request.POST.get('receipt_number', ''),
                    'receipt_type': request.POST.get('receipt_type', receipt_type),
                    'form': form,
                },
            )

    next_type = request.GET.get('type', 'receipt')
    from common.models import SequenceNumber

    next_number = f'PR-{SequenceNumber.get_next_number("payment_receipt")}'
    return render(
        request,
        'payment_receipts/receipt_form.html',
        {
            'customers': customers,
            'suppliers': suppliers,
            'banks': banks,
            'safes': safes,
            'next_number': next_number,
            'receipt_type': next_type,
        },
    )


@screen_permission_required('payment_receipts.paymentreceipt', 'view')
def receipt_detail(request, pk):
    receipt = get_object_or_404(
        PaymentReceipt.objects.select_related('customer', 'supplier', 'bank', 'safe', 'journal_entry'), pk=pk
    )
    return render(request, 'payment_receipts/receipt_detail.html', {'receipt': receipt})


@require_POST
@screen_permission_required('payment_receipts.paymentreceipt', 'edit')
def receipt_post(request, pk):
    receipt = get_object_or_404(PaymentReceipt, pk=pk)
    try:
        receipt.create_journal_entry()
        messages.success(request, f'تم ترحيل السند {receipt.receipt_number} بنجاح')
    except Exception:
        messages.error(request, 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.')
        logger.exception('Posting failed for PaymentReceipt %s', pk)
    return redirect('payment_receipts:detail', pk=pk)


@require_POST
@screen_permission_required('payment_receipts.paymentreceipt', 'edit')
def receipt_allocate(request, pk):
    receipt = get_object_or_404(PaymentReceipt, pk=pk)
    if receipt.is_posted:
        messages.error(request, 'لا يمكن تعديل تخصيص سند مرحل')
        return redirect('payment_receipts:detail', pk=pk)

    from decimal import Decimal

    invoice_ids = request.POST.getlist('invoice_ids')
    amounts = request.POST.getlist('allocation_amounts')

    if not invoice_ids:
        messages.error(request, 'يجب اختيار فاتورة واحدة على الأقل')
        return redirect('payment_receipts:detail', pk=pk)

    total_allocated = Decimal('0')
    allocations = []
    for i, inv_id in enumerate(invoice_ids):
        if not inv_id or i >= len(amounts):
            continue
        try:
            amount = Decimal(amounts[i])
        except (ValueError, TypeError):
            continue
        if amount <= 0:
            continue
        allocations.append((inv_id, amount))
        total_allocated += amount

    if total_allocated > receipt.amount:
        messages.error(request, f'إجمالي التخصيص ({total_allocated}) يتجاوز مبلغ السند ({receipt.amount})')
        return redirect('payment_receipts:detail', pk=pk)

    with transaction.atomic():
        for inv_id, amount in allocations:
            if receipt.receipt_type == 'receipt':
                from sales.models import Customer, SalesInvoice

                invoice = SalesInvoice.objects.select_for_update().get(pk=inv_id)
                invoice.paid_amount += amount
                invoice.calculate_totals()
                invoice.save(update_fields=['paid_amount'])
                if invoice.customer_id:
                    customer = Customer.objects.select_for_update().get(pk=invoice.customer_id)
                    customer.current_balance -= amount
                    customer.save(update_fields=['current_balance'])
            else:
                from purchases.models import PurchaseInvoice, Supplier

                invoice = PurchaseInvoice.objects.select_for_update().get(pk=inv_id)
                invoice.paid_amount += amount
                invoice.calculate_totals()
                invoice.save(update_fields=['paid_amount'])
                if invoice.supplier_id:
                    supplier = Supplier.objects.select_for_update().get(pk=invoice.supplier_id)
                    supplier.current_balance -= amount
                    supplier.save(update_fields=['current_balance'])

    messages.success(request, f'تم تخصيص {total_allocated:,.2f} ج.م من السند على الفواتير')
    return redirect('payment_receipts:detail', pk=pk)


@require_POST
@screen_permission_required('payment_receipts.paymentreceipt', 'delete')
def receipt_delete(request, pk):
    receipt = get_object_or_404(PaymentReceipt, pk=pk)
    if receipt.is_posted:
        messages.error(request, 'لا يمكن حذف سند مرحل — ألغِ الترحيل أولاً')
    else:
        receipt.delete()
        messages.success(request, 'تم حذف السند')
    return redirect('payment_receipts:list')


@screen_permission_required('payment_receipts.paymentreceipt', 'print')
def receipt_print(request, pk):
    from company.models import Company

    receipt = get_object_or_404(PaymentReceipt, pk=pk)
    company = Company.objects.first()
    return render(request, 'payment_receipts/receipt_print.html', {'receipt': receipt, 'company': company})


@screen_permission_required('payment_receipts.paymentreceipt', 'view')
def get_customer_invoices(request):
    from django.http import JsonResponse

    customer_id = request.GET.get('customer_id')
    if not customer_id:
        return JsonResponse([], safe=False)
    invoices = SalesInvoice.objects.filter(customer_id=customer_id, remaining_amount__gt=0, is_posted=True).values(
        'pk', 'invoice_number', 'remaining_amount', 'total_amount'
    )
    return JsonResponse(list(invoices), safe=False)


@screen_permission_required('payment_receipts.paymentreceipt', 'view')
def get_supplier_invoices(request):
    from django.http import JsonResponse

    supplier_id = request.GET.get('supplier_id')
    if not supplier_id:
        return JsonResponse([], safe=False)
    invoices = PurchaseInvoice.objects.filter(supplier_id=supplier_id, remaining_amount__gt=0, is_posted=True).values(
        'pk', 'invoice_number', 'remaining_amount', 'total_amount'
    )
    return JsonResponse(list(invoices), safe=False)
