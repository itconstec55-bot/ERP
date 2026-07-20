from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import SalesQuotation, SalesQuotationLine
from .forms import SalesQuotationForm, SalesQuotationLineFormSet
from sales.models import Customer, SalesInvoice, SalesInvoiceLine
from purchases.models import Product
from common.models import SequenceNumber
from common.permissions import screen_permission_required
import logging

logger = logging.getLogger('accounting')


@screen_permission_required('sales.salesinvoice', 'view')
def quotation_list(request):
    quotations = SalesQuotation.objects.select_related('customer').all()
    status = request.GET.get('status')
    if status:
        quotations = quotations.filter(status=status)
    paginator = Paginator(quotations, 25)
    page = request.GET.get('page')
    quotations_page = paginator.get_page(page)
    return render(request, 'sales_quotation/quotation_list.html', {'quotations': quotations_page, 'status_filter': status})


@screen_permission_required('sales.salesinvoice', 'add')
def quotation_create(request):
    if request.method == 'POST':
        form = SalesQuotationForm(request.POST)
        formset = SalesQuotationLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                quotation = form.save(commit=False)
                quotation.created_by = request.user
                quotation.save()
                formset.instance = quotation
                formset.save()
                quotation.calculate_totals()
            messages.success(request, 'تم إنشاء عرض السعر بنجاح')
            return redirect('sales_quotation:quotation_detail', pk=quotation.pk)
    else:
        form = SalesQuotationForm()
        formset = SalesQuotationLineFormSet()
    products = Product.objects.filter(is_active=True)
    return render(request, 'sales_quotation/quotation_form.html', {
        'form': form, 'formset': formset, 'products': products, 'title': 'عرض سعر جديد',
    })


@screen_permission_required('sales.salesinvoice', 'view')
def quotation_detail(request, pk):
    quotation = get_object_or_404(SalesQuotation.objects.select_related('customer'), pk=pk)
    lines = quotation.lines.select_related('product').all()
    return render(request, 'sales_quotation/quotation_detail.html', {'quotation': quotation, 'lines': lines})


@screen_permission_required('sales.salesinvoice', 'edit')
def quotation_edit(request, pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    if quotation.status in ('converted', 'accepted'):
        messages.error(request, 'لا يمكن تعديل عرض سعر مقبول أو محول')
        return redirect('sales_quotation:quotation_detail', pk=pk)
    if request.method == 'POST':
        form = SalesQuotationForm(request.POST, instance=quotation)
        formset = SalesQuotationLineFormSet(request.POST, instance=quotation)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
                quotation.calculate_totals()
            messages.success(request, 'تم تعديل عرض السعر بنجاح')
            return redirect('sales_quotation:quotation_detail', pk=pk)
    else:
        form = SalesQuotationForm(instance=quotation)
        formset = SalesQuotationLineFormSet(instance=quotation)
    products = Product.objects.filter(is_active=True)
    return render(request, 'sales_quotation/quotation_form.html', {
        'form': form, 'formset': formset, 'products': products, 'quotation': quotation,
        'title': f'تعديل عرض السعر {quotation.quotation_number}',
    })


@require_POST
@screen_permission_required('sales.salesinvoice', 'edit')
def quotation_send(request, pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    quotation.status = 'sent'
    quotation.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'تم إرسال عرض السعر {quotation.quotation_number}')
    return redirect('sales_quotation:quotation_detail', pk=pk)


@require_POST
@screen_permission_required('sales.salesinvoice', 'edit')
def quotation_accept(request, pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    quotation.status = 'accepted'
    quotation.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'تم قبول عرض السعر {quotation.quotation_number}')
    return redirect('sales_quotation:quotation_detail', pk=pk)


@require_POST
@screen_permission_required('sales.salesinvoice', 'edit')
def quotation_reject(request, pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    quotation.status = 'rejected'
    quotation.save(update_fields=['status', 'updated_at'])
    messages.warning(request, f'تم رفض عرض السعر {quotation.quotation_number}')
    return redirect('sales_quotation:quotation_detail', pk=pk)


@require_POST
@screen_permission_required('sales.salesinvoice', 'edit')
def quotation_to_invoice(request, pk):
    quotation = get_object_or_404(SalesQuotation.objects.select_related('customer'), pk=pk)
    if quotation.status in ('expired', 'rejected'):
        messages.error(request, 'لا يمكن تحويل عرض سعر منتهي أو مرفوض')
        return redirect('sales_quotation:quotation_detail', pk=pk)

    with transaction.atomic():
        invoice = SalesInvoice.objects.create(
            invoice_number=SequenceNumber.get_next_number('sales_invoice'),
            customer=quotation.customer,
            date=timezone.now().date(),
            notes=f'محوَّل من عرض السعر {quotation.quotation_number}\n' + (quotation.notes or ''),
            created_by=request.user,
        )
        created = 0
        for line in quotation.lines.select_related('product').all():
            if line.quantity <= 0:
                continue
            SalesInvoiceLine.objects.create(
                invoice=invoice,
                product=line.product,
                quantity=line.quantity,
                unit_price=line.unit_price,
                cost_price=line.product.purchase_price,
                discount_percent=line.discount_percent,
            )
            created += 1
        if created == 0:
            invoice.delete()
            messages.warning(request, 'لا توجد بنود قابلة للتحويل')
            return redirect('sales_quotation:quotation_detail', pk=pk)
        invoice.calculate_totals()
        quotation.status = 'converted'
        quotation.converted_invoice = invoice
        quotation.save(update_fields=['status', 'converted_invoice', 'updated_at'])

    messages.success(request, f'تم إنشاء فاتورة المبيعات {invoice.invoice_number} من عرض السعر')
    return redirect('sales:invoice_detail', pk=invoice.pk)


@require_POST
@screen_permission_required('sales.salesinvoice', 'delete')
def quotation_delete(request, pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    if quotation.status == 'converted':
        messages.error(request, 'لا يمكن حذف عرض سعر محول لفاتورة')
    else:
        quotation.delete()
        messages.success(request, 'تم حذف عرض السعر')
    return redirect('sales_quotation:quotation_list')
