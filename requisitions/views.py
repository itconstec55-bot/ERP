from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from common.permissions import screen_permission_required
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from purchases.models import Product, Supplier

from .forms import RequisitionForm, RequisitionLineFormSet
from .models import Requisition

logger = __import__('logging').getLogger('accounting')

RFQ_THRESHOLD = 10000


ESCALATION_DAYS = 3


def _days_pending(reference_date, today=None):
    if reference_date is None:
        return 0
    if today is None:
        today = timezone.localdate()
    return (today - reference_date).days


def _is_escalated(days):
    return days >= ESCALATION_DAYS


@screen_permission_required('requisitions.requisition', 'view')
def req_list(request):
    reqs = Requisition.objects.select_related('requested_by', 'cost_center', 'created_by').all()
    status = request.GET.get('status')
    if status:
        reqs = reqs.filter(status=status)
    priority = request.GET.get('priority')
    if priority:
        reqs = reqs.filter(priority=priority)
    paginator = Paginator(reqs, 25)
    page = request.GET.get('page')
    reqs_page = paginator.get_page(page)
    return render(
        request, 'requisitions/req_list.html', {'reqs': reqs_page, 'status_filter': status, 'priority_filter': priority}
    )


@screen_permission_required('requisitions.requisition', 'add')
def req_create(request):
    if request.method == 'POST':
        form = RequisitionForm(request.POST)
        formset = RequisitionLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                req = form.save(commit=False)
                req.requested_by = request.user
                req.created_by = request.user
                req.save()
                formset.instance = req
                formset.save()
            if req.lines.count() == 0:
                messages.warning(request, 'تم حفظ طلب الشراء لكنه لا يحتوي على بنود')
            if not req.cost_center:
                messages.warning(request, 'لم يتم تحديد مركز تكلفة للطلب — يُفضّل تحديده قبل الاعتماد')
            messages.success(request, f'تم إنشاء طلب الشراء {req.number} بنجاح')
            return redirect('requisitions:req_detail', pk=req.pk)
    else:
        form = RequisitionForm(initial={'date': date.today()})
        formset = RequisitionLineFormSet()
    products = Product.objects.filter(is_active=True)
    return render(
        request,
        'requisitions/req_form.html',
        {'form': form, 'formset': formset, 'products': products, 'title': 'إنشاء طلب شراء جديد'},
    )


@screen_permission_required('requisitions.requisition', 'view')
def req_detail(request, pk):
    req = get_object_or_404(Requisition.objects.select_related('requested_by', 'cost_center', 'created_by'), pk=pk)
    lines = req.lines.select_related('product', 'uom').all()
    today = timezone.localdate()
    days = _days_pending(req.date, today)
    return render(
        request,
        'requisitions/req_detail.html',
        {
            'req': req,
            'lines': lines,
            'days_pending': days,
            'is_escalated': _is_escalated(days),
            'threshold': RFQ_THRESHOLD,
        },
    )


@screen_permission_required('requisitions.requisition', 'edit')
def req_edit(request, pk):
    req = get_object_or_404(Requisition, pk=pk)
    if req.status not in ('draft', 'rejected'):
        messages.error(request, 'لا يمكن تعديل طلب شراء غير مسودة أو مرفوض')
        return redirect('requisitions:req_detail', pk=req.pk)
    if request.method == 'POST':
        form = RequisitionForm(request.POST, instance=req)
        formset = RequisitionLineFormSet(request.POST, instance=req)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, f'تم تعديل طلب الشراء {req.number} بنجاح')
            return redirect('requisitions:req_detail', pk=req.pk)
    else:
        form = RequisitionForm(instance=req)
        formset = RequisitionLineFormSet(instance=req)
    products = Product.objects.filter(is_active=True)
    return render(
        request,
        'requisitions/req_form.html',
        {'form': form, 'formset': formset, 'products': products, 'req': req, 'title': f'تعديل طلب الشراء {req.number}'},
    )


@require_POST
@screen_permission_required('requisitions.requisition', 'edit')
def req_submit(request, pk):
    req = get_object_or_404(Requisition, pk=pk)
    if req.status != 'draft':
        messages.error(request, 'لا يمكن تقديم طلب شراء غير مسودة')
        return redirect('requisitions:req_detail', pk=req.pk)
    if req.lines.count() == 0:
        messages.error(request, 'لا يمكن تقديم طلب شراء بدون بنود')
        return redirect('requisitions:req_detail', pk=req.pk)
    req.status = 'pending'
    req.save(update_fields=['status', 'updated_at'])
    if not req.cost_center:
        messages.warning(request, 'تم التقديم بدون مركز تكلفة — يُفضّل تحديده قبل الاعتماد')
    else:
        messages.success(request, f'تم تقديم طلب الشراء {req.number} للموافقة')
    return redirect('requisitions:req_detail', pk=req.pk)


@require_POST
@screen_permission_required('requisitions.requisition', 'edit')
def req_approve(request, pk):
    req = get_object_or_404(Requisition, pk=pk)
    if req.status != 'pending':
        messages.error(request, 'لا يمكن اعتماد طلب شراء غير بانتظار الموافقة')
        return redirect('requisitions:req_detail', pk=req.pk)
    req.status = 'approved'
    req.save(update_fields=['status', 'updated_at'])
    if not req.cost_center:
        messages.warning(request, 'تم الاعتماد بدون مركز تكلفة — يُنصح بتحديده قبل تحويل الطلب')
    else:
        messages.success(request, f'تم اعتماد طلب الشراء {req.number}')
    return redirect('requisitions:req_detail', pk=req.pk)


@require_POST
@screen_permission_required('requisitions.requisition', 'edit')
def req_reject(request, pk):
    req = get_object_or_404(Requisition, pk=pk)
    if req.status != 'pending':
        messages.error(request, 'لا يمكن رفض طلب شراء غير بانتظار الموافقة')
        return redirect('requisitions:req_detail', pk=req.pk)
    reason = request.POST.get('reason', '').strip()
    if not reason:
        messages.error(request, 'يجب إدخال سبب الرفض')
        return redirect('requisitions:req_detail', pk=req.pk)
    req.status = 'rejected'
    req.notes = (req.notes or '') + f'\nسبب الرفض: {reason}'
    req.save(update_fields=['status', 'notes', 'updated_at'])
    messages.success(request, f'تم رفض طلب الشراء {req.number}')
    return redirect('requisitions:req_detail', pk=req.pk)


@screen_permission_required('requisitions.requisition', 'edit')
def req_convert(request, pk):
    req = get_object_or_404(Requisition.objects.select_related('cost_center', 'created_by'), pk=pk)
    if req.status != 'approved':
        messages.error(request, 'لا يمكن تحويل طلب شراء غير معتمد')
        return redirect('requisitions:req_detail', pk=req.pk)

    total = req.total
    force_rfq = total > RFQ_THRESHOLD
    suppliers = Supplier.objects.filter(is_active=True)

    if request.method == 'POST':
        action = request.POST.get('convert_action')
        if action == 'rfq':
            return _convert_to_rfq(request, req)
        if action == 'po':
            if force_rfq:
                messages.error(
                    request,
                    f'لا يمكن إنشاء أمر شراء مباشر لطلب تتجاوز قيمته {RFQ_THRESHOLD} ج.م — '
                    f'يجب المرور بطلب عروض الأسعار (RFQ)',
                )
                return redirect('requisitions:req_convert', pk=req.pk)
            supplier_id = request.POST.get('supplier')
            if not supplier_id:
                messages.error(request, 'يجب اختيار مورد لإنشاء أمر الشراء المباشر')
                return redirect('requisitions:req_convert', pk=req.pk)
            return _convert_to_po(request, req, supplier_id)
        messages.error(request, 'إجراء تحويل غير صحيح')
        return redirect('requisitions:req_convert', pk=req.pk)

    return render(
        request,
        'requisitions/req_convert.html',
        {'req': req, 'total': total, 'threshold': RFQ_THRESHOLD, 'force_rfq': force_rfq, 'suppliers': suppliers},
    )


@transaction.atomic
def _convert_to_rfq(request, req):
    try:
        from rfq.models import RFQ, RFQLine
    except ImportError:
        messages.error(request, 'تطبيق طلبات عروض الأسعار (rfq) غير متاح بعد')
        return redirect('requisitions:req_convert', pk=req.pk)

    rfq_fields = {f.name for f in RFQ._meta.get_fields()}
    kwargs = {'requisition': req}
    if 'date' in rfq_fields:
        kwargs['date'] = req.date
    if 'status' in rfq_fields:
        kwargs['status'] = 'draft'
    if 'notes' in rfq_fields:
        kwargs['notes'] = f'محوّل من طلب الشراء {req.number}'
    if 'created_by' in rfq_fields:
        kwargs['created_by'] = request.user
    if 'cost_center' in rfq_fields:
        kwargs['cost_center'] = req.cost_center

    rfq = RFQ.objects.create(**kwargs)

    line_fields = {f.name for f in RFQLine._meta.get_fields()}
    for line in req.lines.select_related('product', 'uom').all():
        lkwargs = {'requisition': rfq, 'product': line.product, 'quantity': line.quantity}
        if 'estimated_unit_price' in line_fields:
            lkwargs['estimated_unit_price'] = line.estimated_unit_price or 0
        if 'uom' in line_fields:
            lkwargs['uom'] = line.uom
        if 'notes' in line_fields:
            lkwargs['notes'] = line.notes
        if 'required_date' in line_fields:
            lkwargs['required_date'] = line.required_date
        RFQLine.objects.create(**lkwargs)

    req.status = 'ordered'
    req.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'تم إنشاء طلب عروض الأسعار من طلب الشراء {req.number}')
    if hasattr(rfq, 'get_absolute_url'):
        return redirect(rfq.get_absolute_url())
    return redirect('requisitions:req_detail', pk=req.pk)


@transaction.atomic
def _convert_to_po(request, req, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id, is_active=True)
    po = PurchaseOrder(
        supplier=supplier,
        date=req.date,
        status='draft',
        cost_center=req.cost_center,
        expected_date=req.need_by_date,
        notes=f'محوّل مباشرة من طلب الشراء {req.number}\n' + (req.notes or ''),
        created_by=request.user,
    )
    po.save()
    for line in req.lines.select_related('product').all():
        PurchaseOrderLine.objects.create(
            order=po, product=line.product, quantity=line.quantity, unit_price=line.estimated_unit_price or 0
        )
    req.status = 'ordered'
    req.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'تم إنشاء أمر الشراء {po.order_number} مباشرة من طلب الشراء')
    return redirect('purchase_orders:po_detail', pk=po.pk)


@screen_permission_required('requisitions.requisition', 'view')
def workflow_dashboard(request):
    today = timezone.localdate()

    pending_reqs = []
    for r in Requisition.objects.filter(status='pending').select_related('requested_by', 'cost_center'):
        days = _days_pending(r.date, today)
        pending_reqs.append(
            {
                'pk': r.pk,
                'number': r.number,
                'title': f'طلب شراء {r.number}',
                'subtitle': f'بواسطة {r.requested_by}',
                'status': r.status,
                'status_display': r.get_status_display(),
                'days': days,
                'escalated': _is_escalated(days),
                'url': r.get_absolute_url(),
                'cost_center': r.cost_center,
            }
        )

    rfqs_overdue = []
    try:
        from rfq.models import RFQ

        rfq_qs = RFQ.objects.filter(status='sent', valid_until__lt=today)
        if hasattr(RFQ, 'requisition'):
            rfq_qs = rfq_qs.select_related('requisition')
        for q in rfq_qs:
            ref = getattr(q, 'date', None) or getattr(getattr(q, 'requisition', None), 'date', None)
            days = _days_pending(getattr(q, 'valid_until', None), today)
            overdue_days = _days_pending(ref, today)
            rfqs_overdue.append(
                {
                    'pk': q.pk,
                    'number': getattr(q, 'number', str(q.pk)),
                    'title': f'طلب عروض أسعار {getattr(q, "number", q.pk)}',
                    'subtitle': f'انتهت مهلة الرد: {getattr(q, "valid_until", "-")}',
                    'status': 'sent',
                    'status_display': 'مُرسل',
                    'days': days,
                    'escalated': True,
                    'overdue_days': max(days, 0),
                    'url': getattr(q, 'get_absolute_url', lambda: '#')(),
                    'cost_center': getattr(getattr(q, 'requisition', None), 'cost_center', None),
                }
            )
    except ImportError:
        rfqs_overdue = []

    pos_waiting = []
    for po in PurchaseOrder.objects.filter(status__in=['sent', 'approved']).select_related('supplier'):
        days = _days_pending(po.date, today)
        pos_waiting.append(
            {
                'pk': po.pk,
                'number': po.order_number,
                'title': f'أمر شراء {po.order_number}',
                'subtitle': f'المورد: {po.supplier.name}',
                'status': po.status,
                'status_display': po.get_status_display(),
                'days': days,
                'escalated': _is_escalated(days),
                'url': po.get_absolute_url(),
                'cost_center': None,
            }
        )

    return render(
        request,
        'requisitions/workflow_dashboard.html',
        {
            'today': today,
            'pending_reqs': pending_reqs,
            'rfqs_overdue': rfqs_overdue,
            'pos_waiting': pos_waiting,
            'escalation_days': ESCALATION_DAYS,
        },
    )


@screen_permission_required('requisitions.requisition', 'view')
def pending_approvals(request):
    today = timezone.localdate()

    pending_reqs = []
    for r in Requisition.objects.filter(status='pending').select_related('requested_by', 'cost_center'):
        days = _days_pending(r.date, today)
        pending_reqs.append(
            {
                'pk': r.pk,
                'number': r.number,
                'title': f'طلب شراء {r.number}',
                'subtitle': f'بواسطة {r.requested_by}',
                'status': r.status,
                'status_display': r.get_status_display(),
                'days': days,
                'escalated': _is_escalated(days),
                'url': r.get_absolute_url(),
                'cost_center': r.cost_center,
            }
        )

    pos_waiting = []
    for po in PurchaseOrder.objects.filter(status='sent').select_related('supplier'):
        days = _days_pending(po.date, today)
        pos_waiting.append(
            {
                'pk': po.pk,
                'number': po.order_number,
                'title': f'أمر شراء {po.order_number}',
                'subtitle': f'المورد: {po.supplier.name}',
                'status': po.status,
                'status_display': po.get_status_display(),
                'days': days,
                'escalated': _is_escalated(days),
                'url': po.get_absolute_url(),
                'cost_center': None,
            }
        )

    return render(
        request,
        'requisitions/pending_approvals.html',
        {'today': today, 'pending_reqs': pending_reqs, 'pos_waiting': pos_waiting, 'escalation_days': ESCALATION_DAYS},
    )
