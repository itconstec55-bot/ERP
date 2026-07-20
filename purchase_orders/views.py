from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.views.decorators.http import require_POST
from django.utils import timezone
import logging

from common.permissions import screen_permission_required
from purchases.models import Supplier, Product, PurchaseInvoice, PurchaseInvoiceLine
from budget.models import Budget
from common.models import SequenceNumber
from .models import PurchaseOrder, PurchaseOrderLine
from .forms import PurchaseOrderForm, PurchaseOrderLineFormSet
from decimal import Decimal

logger = logging.getLogger('accounting')


def _accrue_budget(order, amount):
    """استهلاك/تراجع مبلغ أمر الشراء من الموازنة المعتمدة لمركز التكلفة."""
    if not order.cost_center:
        return
    budgets = Budget.objects.filter(cost_center=order.cost_center, status='active')
    if budgets.exists():
        b = budgets.first()
        b.actual_amount = (b.actual_amount or Decimal('0')) + amount
        b.save(update_fields=['actual_amount', 'updated_at'])


@screen_permission_required('purchase_orders.purchaseorder', 'view')
def po_list(request):
    orders = PurchaseOrder.objects.select_related('supplier', 'created_by').all()
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
    supplier_id = request.GET.get('supplier')
    if supplier_id:
        orders = orders.filter(supplier_id=supplier_id)
    paginator = Paginator(orders, 25)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    return render(request, 'purchase_orders/po_list.html', {
        'orders': orders_page,
        'status_filter': status,
        'suppliers': Supplier.objects.filter(is_active=True),
    })


@screen_permission_required('purchase_orders.purchaseorder', 'add')
def po_create(request):
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        formset = PurchaseOrderLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.created_by = request.user
                order.save()
                formset.instance = order
                formset.save()
            messages.success(request, 'تم إنشاء أمر الشراء بنجاح')
            return redirect('purchase_orders:po_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm()
        formset = PurchaseOrderLineFormSet()
    products = Product.objects.filter(is_active=True)
    return render(request, 'purchase_orders/po_form.html', {
        'form': form,
        'formset': formset,
        'products': products,
        'title': 'إنشاء أمر شراء جديد',
    })


@screen_permission_required('purchase_orders.purchaseorder', 'view')
def po_detail(request, pk):
    order = get_object_or_404(PurchaseOrder.objects.select_related('supplier'), pk=pk)
    lines = order.lines.select_related('product').all()
    return render(request, 'purchase_orders/po_detail.html', {
        'order': order,
        'lines': lines,
        'budget': order.budget_check(),
    })


@screen_permission_required('purchase_orders.purchaseorder', 'edit')
def po_edit(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.status in ('received', 'cancelled'):
        messages.error(request, 'لا يمكن تعديل أمر شراء مستلم أو ملغي')
        return redirect('purchase_orders:po_detail', pk=order.pk)
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order)
        formset = PurchaseOrderLineFormSet(request.POST, instance=order)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, 'تم تعديل أمر الشراء بنجاح')
            return redirect('purchase_orders:po_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm(instance=order)
        formset = PurchaseOrderLineFormSet(instance=order)
    products = Product.objects.filter(is_active=True)
    return render(request, 'purchase_orders/po_form.html', {
        'form': form,
        'formset': formset,
        'products': products,
        'order': order,
        'title': f'تعديل أمر الشراء {order.order_number}',
    })


@require_POST
@screen_permission_required('purchase_orders.purchaseorder', 'edit')
def po_approve(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.status in ('cancelled', 'received'):
        messages.error(request, 'لا يمكن اعتماد أمر شراء ملغي أو مستلم')
    else:
        check = order.budget_check()
        if order.cost_center and not check['ok']:
            messages.error(
                request,
                f'تعذّر الاعتماد: {check["message"]} (المتاح {check["available"]} ج.م)'
            )
            return redirect('purchase_orders:po_detail', pk=order.pk)
        if not order.cost_center:
            messages.warning(
                request,
                'تم الاعتماد دون تحديد مركز تكلفة — يُفضّل ربط الأمر بمركز تكلفة للمتابعة الموازنية'
            )
        order.status = 'approved'
        order.save(update_fields=['status', 'updated_at'])
        _accrue_budget(order, order.subtotal)
        messages.success(request, f'تم اعتماد أمر شراء {order.order_number}')
    return redirect('purchase_orders:po_detail', pk=order.pk)


@require_POST
@screen_permission_required('purchase_orders.purchaseorder', 'edit')
def po_cancel(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.status == 'received':
        messages.error(request, 'لا يمكن إلغاء أمر شراء مستلم')
    else:
        was_approved = order.status == 'approved'
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        if was_approved:
            _accrue_budget(order, -order.subtotal)
        messages.success(request, f'تم إلغاء أمر الشراء {order.order_number}')
    return redirect('purchase_orders:po_detail', pk=order.pk)


@require_POST
@screen_permission_required('purchase_orders.purchaseorder', 'edit')
def po_to_invoice(request, pk):
    order = get_object_or_404(PurchaseOrder.objects.select_related('supplier'), pk=pk)
    if order.status == 'cancelled':
        messages.error(request, 'لا يمكن تحويل أمر شراء ملغي إلى فاتورة')
        return redirect('purchase_orders:po_detail', pk=order.pk)

    with transaction.atomic():
        invoice = PurchaseInvoice.objects.create(
            invoice_number=SequenceNumber.get_next_number('purchase_invoice'),
            supplier=order.supplier,
            date=order.date,
            notes=f'محوّلة من أمر الشراء {order.order_number}\n' + (order.notes or ''),
            created_by=request.user,
        )
        created = 0
        for line in order.lines.select_related('product').all():
            remaining = line.quantity - line.received_quantity
            if remaining <= 0:
                # تم استلامه بالكامل وترحيله؛ لا نكرر الكمية
                continue
            PurchaseInvoiceLine.objects.create(
                invoice=invoice,
                product=line.product,
                quantity=remaining,
                unit_price=line.unit_price,
                discount_percent=0,
                total_price=remaining * line.unit_price,
            )
            created += 1
        if created == 0:
            invoice.delete()
            messages.warning(request, 'لا توجد بنود قابلة للتحويل (تم ترحيل الكميات بالكامل)')
            return redirect('purchase_orders:po_detail', pk=order.pk)
        invoice.calculate_totals()
        invoice.approved_by = request.user
        invoice.approved_at = timezone.now()
        invoice.save(update_fields=['approved_by', 'approved_at'])
        try:
            invoice.create_journal_entry()
            messages.success(request, f'تم إنشاء فاتورة المشتريات {invoice.invoice_number} وترحيلها محاسبياً من أمر الشراء')
        except Exception as exc:
            logger.warning('تعذّر الترحيل التلقائي لفاتورة %s: %s', invoice.invoice_number, exc)
            messages.warning(request, f'تم إنشاء الفاتورة {invoice.invoice_number} ولكنها تحتاج ترحيلاً يدوياً')

    return redirect('purchases:invoice_detail', pk=invoice.pk)
