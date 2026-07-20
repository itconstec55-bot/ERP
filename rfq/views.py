from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from common.permissions import screen_permission_required
from purchases.models import Product

from .forms import QuotationForm, QuotationLineFormSet, RFQForm, RFQLineFormSet
from .models import RFQ, Quotation

logger = __import__('logging').getLogger('accounting')


@screen_permission_required('rfq.rfq', 'view')
def rfq_list(request):
    rfqs = RFQ.objects.select_related('requested_by', 'cost_center').all()
    status = request.GET.get('status')
    if status:
        rfqs = rfqs.filter(status=status)
    paginator = Paginator(rfqs, 25)
    page = request.GET.get('page')
    rfqs_page = paginator.get_page(page)
    return render(
        request, 'rfq/rfq_list.html', {'rfqs': rfqs_page, 'status_filter': status, 'status_choices': RFQ.STATUS_CHOICES}
    )


@screen_permission_required('rfq.rfq', 'add')
def rfq_create(request):
    if request.method == 'POST':
        form = RFQForm(request.POST, user=request.user)
        formset = RFQLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                rfq = form.save(commit=False)
                rfq.created_by = request.user
                if not rfq.requested_by:
                    rfq.requested_by = request.user
                rfq.save()
                formset.instance = rfq
                formset.save()
            messages.success(request, 'تم إنشاء طلب عروض الأسعار بنجاح')
            return redirect('rfq:rfq_detail', pk=rfq.pk)
    else:
        form = RFQForm(user=request.user)
        formset = RFQLineFormSet()
    return render(
        request,
        'rfq/rfq_form.html',
        {
            'form': form,
            'formset': formset,
            'products': Product.objects.filter(is_active=True),
            'title': 'إنشاء طلب عروض أسعار جديد',
        },
    )


@screen_permission_required('rfq.rfq', 'view')
def rfq_detail(request, pk):
    rfq = get_object_or_404(
        RFQ.objects.select_related('requested_by', 'cost_center', 'requisition', 'created_by'), pk=pk
    )
    lines = rfq.lines.select_related('product').all()
    quotations = rfq.quotations.select_related('supplier').prefetch_related('lines__product').all()

    # جدول مقارنة: لكل بند طلب عمود لكل عرض سعر
    comparison = []
    for line in lines:
        row = {'line': line, 'cells': []}
        lowest = None
        for q in quotations:
            qline = q.lines.filter(rfq_line=line).first()
            price = qline.unit_price if qline else None
            if price is not None and (lowest is None or price < lowest):
                lowest = price
            row['cells'].append(
                {'quotation': q, 'qline': qline, 'price': price, 'delivery': qline.delivery_days if qline else None}
            )
        row['lowest'] = lowest
        comparison.append(row)

    return render(
        request, 'rfq/rfq_detail.html', {'rfq': rfq, 'lines': lines, 'quotations': quotations, 'comparison': comparison}
    )


@screen_permission_required('rfq.rfq', 'edit')
def rfq_edit(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if rfq.status in ('closed', 'cancelled'):
        messages.error(request, 'لا يمكن تعديل طلب عروض أسعار مغلق أو ملغي')
        return redirect('rfq:rfq_detail', pk=rfq.pk)
    if request.method == 'POST':
        form = RFQForm(request.POST, instance=rfq, user=request.user)
        formset = RFQLineFormSet(request.POST, instance=rfq)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, 'تم تعديل طلب عروض الأسعار بنجاح')
            return redirect('rfq:rfq_detail', pk=rfq.pk)
    else:
        form = RFQForm(instance=rfq, user=request.user)
        formset = RFQLineFormSet(instance=rfq)
    return render(
        request,
        'rfq/rfq_form.html',
        {
            'form': form,
            'formset': formset,
            'products': Product.objects.filter(is_active=True),
            'rfq': rfq,
            'title': f'تعديل طلب عروض الأسعار {rfq.number}',
        },
    )


@require_POST
@screen_permission_required('rfq.rfq', 'edit')
def rfq_send(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if rfq.lines.count() == 0:
        messages.error(request, 'لا يمكن إرسال طلب عروض أسعار بدون بنود')
        return redirect('rfq:rfq_detail', pk=rfq.pk)
    if rfq.status != 'draft':
        messages.error(request, 'يمكن إرسال الطلبات في حالة مسودة فقط')
        return redirect('rfq:rfq_detail', pk=rfq.pk)
    rfq.status = 'sent'
    if not rfq.valid_until:
        rfq.valid_until = timezone.localdate() + timezone.timedelta(days=7)
    rfq.save(update_fields=['status', 'valid_until', 'updated_at'])
    messages.success(request, f'تم إرسال طلب عروض الأسعار {rfq.number}')
    return redirect('rfq:rfq_detail', pk=rfq.pk)


@require_POST
@screen_permission_required('rfq.rfq', 'edit')
def rfq_close(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if rfq.status != 'sent':
        messages.error(request, 'يمكن إغلاق الطلبات المرسلة فقط')
        return redirect('rfq:rfq_detail', pk=rfq.pk)
    rfq.status = 'closed'
    rfq.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'تم إغلاق طلب عروض الأسعار {rfq.number}')
    return redirect('rfq:rfq_detail', pk=rfq.pk)


@screen_permission_required('rfq.rfq', 'add')
def quotation_create(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if rfq.status not in ('draft', 'sent'):
        messages.error(request, 'لا يمكن إضافة عروض أسعار لطلب مغلق أو ملغي')
        return redirect('rfq:rfq_detail', pk=rfq.pk)
    if request.method == 'POST':
        form = QuotationForm(request.POST)
        formset = QuotationLineFormSet(request.POST, rfq=rfq)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                quotation = form.save(commit=False)
                quotation.rfq = rfq
                quotation.created_by = request.user
                quotation.save()
                formset.instance = quotation
                formset.save()
            messages.success(request, 'تم تسجيل عرض السعر بنجاح')
            return redirect('rfq:rfq_detail', pk=rfq.pk)
    else:
        form = QuotationForm()
        formset = QuotationLineFormSet(rfq=rfq)
    return render(
        request,
        'rfq/quotation_form.html',
        {
            'form': form,
            'formset': formset,
            'rfq': rfq,
            'products': Product.objects.filter(is_active=True),
            'title': f'إضافة عرض سعر لطلب {rfq.number}',
        },
    )


@require_POST
@screen_permission_required('rfq.rfq', 'edit')
def quotation_accept(request, pk):
    quotation = get_object_or_404(Quotation.objects.select_related('rfq'), pk=pk)
    if quotation.lines.count() == 0:
        messages.error(request, 'لا يمكن قبول عرض سعر بدون بنود')
        return redirect('rfq:rfq_detail', pk=quotation.rfq.pk)
    with transaction.atomic():
        Quotation.objects.filter(rfq=quotation.rfq).exclude(pk=quotation.pk).update(
            status='rejected', updated_at=timezone.now()
        )
        quotation.status = 'accepted'
        quotation.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'تم قبول عرض السعر من {quotation.supplier.name} ورفض البقية')
    return redirect('rfq:rfq_detail', pk=quotation.rfq.pk)


@require_POST
@screen_permission_required('rfq.rfq', 'edit')
def rfq_convert_to_po(request, pk):
    rfq = get_object_or_404(RFQ.objects.select_related('cost_center'), pk=pk)
    accepted = rfq.quotations.filter(status='accepted')
    if accepted.count() != 1:
        messages.error(request, 'يجب قبول عرض سعر واحد بالضبط قبل التحويل إلى أمر شراء')
        return redirect('rfq:rfq_detail', pk=rfq.pk)

    quotation = accepted.first()
    from purchase_orders.models import PurchaseOrder, PurchaseOrderLine

    with transaction.atomic():
        po = PurchaseOrder.objects.create(
            supplier=quotation.supplier,
            date=timezone.localdate(),
            status='draft',
            cost_center=rfq.cost_center,
            expected_date=rfq.valid_until,
            notes=f'محوّل من طلب عروض الأسعار {rfq.number}\n' + (rfq.notes or ''),
            created_by=request.user,
        )
        created = 0
        for qline in quotation.lines.select_related('product').all():
            from decimal import Decimal

            unit_price = qline.unit_price or Decimal('0')
            if qline.quantity and qline.discount:
                unit_price = unit_price - (Decimal(qline.discount) / Decimal(qline.quantity))
            PurchaseOrderLine.objects.create(
                order=po,
                product=qline.product,
                quantity=qline.quantity,
                unit_price=unit_price,
                received_quantity=0,
                notes=f'خصم {qline.discount} - أيام تسليم {qline.delivery_days or 0}',
            )
            created += 1
        if created == 0:
            po.delete()
            messages.error(request, 'لا توجد بنود في عرض السعر المقبول للتحويل')
            return redirect('rfq:rfq_detail', pk=rfq.pk)
        rfq.status = 'closed'
        rfq.save(update_fields=['status', 'updated_at'])

    messages.success(request, f'تم إنشاء أمر الشراء {po.order_number} من طلب عروض الأسعار')
    return redirect('purchase_orders:po_detail', pk=po.pk)


@screen_permission_required('rfq.rfq', 'view')
def pending_quotations(request):
    today = timezone.localdate()
    overdue = RFQ.objects.filter(status='sent', valid_until__lt=today).select_related('requested_by', 'cost_center')
    open_sent = RFQ.objects.filter(status='sent').select_related('requested_by', 'cost_center')
    return render(request, 'rfq/pending_quotations.html', {'overdue': overdue, 'open_sent': open_sent, 'today': today})
