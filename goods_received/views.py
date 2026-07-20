from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from decimal import Decimal
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
import uuid
import logging

from common.permissions import screen_permission_required
from purchases.models import Supplier, Product, PurchaseInvoice, PurchaseInvoiceLine
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from common.models import SequenceNumber
from warehouses.models import WarehouseProduct, StockMovement, Warehouse, InventoryCostLayer
from .models import GoodsReceivedNote, GoodsReceivedLine
from .forms import GoodsReceivedNoteForm, GoodsReceivedLineFormSet

logger = logging.getLogger('accounting')


@screen_permission_required('goods_received.grn', 'view')
def grn_list(request):
    notes = GoodsReceivedNote.objects.select_related('supplier', 'purchase_order', 'created_by').all()
    status = request.GET.get('status')
    if status:
        notes = notes.filter(status=status)
    paginator = Paginator(notes, 25)
    page = request.GET.get('page')
    notes_page = paginator.get_page(page)
    return render(request, 'goods_received/grn_list.html', {
        'notes': notes_page,
        'status_filter': status,
    })


@screen_permission_required('goods_received.grn', 'add')
def grn_create(request):
    if request.method == 'POST':
        form = GoodsReceivedNoteForm(request.POST)
        formset = GoodsReceivedLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                grn = form.save(commit=False)
                grn.created_by = request.user
                grn.save()
                formset.instance = grn
                formset.save()
            messages.success(request, 'تم إنشاء إيصال الاستلام بنجاح')
            return redirect('goods_received:grn_detail', pk=grn.pk)
    else:
        form = GoodsReceivedNoteForm()
        formset = GoodsReceivedLineFormSet()
    products = Product.objects.filter(is_active=True)
    return render(request, 'goods_received/grn_form.html', {
        'form': form,
        'formset': formset,
        'products': products,
        'title': 'إنشاء إيصال استلام جديد',
    })


@screen_permission_required('goods_received.grn', 'view')
def grn_detail(request, pk):
    grn = get_object_or_404(
        GoodsReceivedNote.objects.select_related('supplier', 'purchase_order'), pk=pk
    )
    lines = grn.lines.select_related('product', 'purchase_order_line').all()
    return render(request, 'goods_received/grn_detail.html', {
        'grn': grn,
        'lines': lines,
    })


@require_POST
@screen_permission_required('goods_received.grn', 'edit')
def grn_confirm(request, pk):
    grn = get_object_or_404(GoodsReceivedNote, pk=pk)
    if grn.status == 'confirmed':
        messages.warning(request, 'إيصال الاستلام مؤكد بالفعل')
        return redirect('goods_received:grn_detail', pk=grn.pk)

    with transaction.atomic():
        for line in grn.lines.select_related('product', 'purchase_order_line').all():
            # 1) تحديث الكمية المستلمة في بند أمر الشراء
            po_line = line.purchase_order_line
            if po_line is not None:
                po_line = PurchaseOrderLine.objects.select_for_update().get(pk=po_line.pk)
                new_received = po_line.received_quantity + line.quantity_received
                if new_received > po_line.quantity:
                    new_received = po_line.quantity
                po_line.received_quantity = new_received
                po_line.save(update_fields=['received_quantity'])

            # 2) إنشاء حركة مخزون وارد وزيادة رصيد المخزن
            warehouse = grn.warehouse or Warehouse.objects.first()
            if warehouse:
                StockMovement.objects.create(
                    movement_number=f"GRN-{grn.grn_number}-{line.product.code}-{uuid.uuid4().hex[:6]}",
                    movement_type='in',
                    warehouse=warehouse,
                    product=line.product,
                    quantity=line.quantity_received,
                    unit_cost=line.unit_price,
                    reference_number=grn.grn_number,
                    notes=line.notes or '',
                    performed_by=request.user,
                    date=grn.date,
                )
                wp, _ = WarehouseProduct.objects.get_or_create(
                    warehouse=warehouse, product=line.product,
                    defaults={'quantity': Decimal('0')},
                )
                wp.quantity = (wp.quantity or Decimal('0')) + line.quantity_received
                wp.save(update_fields=['quantity'])

                # إضافة طبقة تكلفة FIFO
                InventoryCostLayer.add_layer(
                    product=line.product,
                    warehouse=warehouse,
                    quantity=line.quantity_received,
                    unit_cost=line.unit_price,
                    reference_number=grn.grn_number,
                    date=grn.date,
                )

        # 3) تحديث حالة أمر الشراء إلى مستلم إن اكتمل الاستلام
        po = grn.purchase_order
        if po is not None:
            po.refresh_from_db()
            if po.lines.exists() and all(l.received_quantity >= l.quantity for l in po.lines.all()):
                po.status = 'received'
                po.save(update_fields=['status', 'updated_at'])

        grn.status = 'confirmed'
        grn.save(update_fields=['status', 'updated_at'])

    # فحص المخزون المنخفض بعد الاستلام
    try:
        from notifications.utils import notify_low_stock
        from django.db.models import F
        low_stock_products = WarehouseProduct.objects.filter(
            quantity__lte=F('minimum_quantity'),
            minimum_quantity__gt=0
        ).select_related('product')[:10]
        for wp in low_stock_products:
            notify_low_stock(wp.product, wp.quantity, wp.minimum_quantity)
    except Exception:
        pass

    messages.success(request, f'تم تأكيد إيصال الاستلام {grn.grn_number}')
    return redirect('goods_received:grn_detail', pk=grn.pk)


@require_POST
@screen_permission_required('goods_received.grn', 'edit')
def grn_to_invoice(request, pk):
    grn = get_object_or_404(GoodsReceivedNote.objects.select_related('supplier'), pk=pk)
    if grn.status != 'confirmed':
        messages.error(request, 'يجب تأكيد إيصال الاستلام أولاً قبل تحويله إلى فاتورة')
        return redirect('goods_received:grn_detail', pk=grn.pk)

    with transaction.atomic():
        invoice = PurchaseInvoice.objects.create(
            invoice_number=SequenceNumber.get_next_number('purchase_invoice'),
            supplier=grn.supplier,
            date=grn.date,
            notes=f'محوَّل من إيصال الاستلام {grn.grn_number}\n' + (grn.notes or ''),
            created_by=request.user,
        )
        created = 0
        for line in grn.lines.select_related('product').all():
            if line.quantity_received <= 0:
                continue
            PurchaseInvoiceLine.objects.create(
                invoice=invoice,
                product=line.product,
                quantity=line.quantity_received,
                unit_price=line.unit_price,
                discount_percent=0,
                total_price=line.quantity_received * line.unit_price,
            )
            created += 1
        if created == 0:
            invoice.delete()
            messages.warning(request, 'لا توجد بنود قابلة للتحويل')
            return redirect('goods_received:grn_detail', pk=grn.pk)
        invoice.calculate_totals()
        invoice.approved_by = request.user
        invoice.approved_at = timezone.now()
        invoice.save(update_fields=['approved_by', 'approved_at'])
        try:
            invoice.create_journal_entry()
            messages.success(request, f'تم إنشاء فاتورة المشتريات {invoice.invoice_number} وترحيلها محاسبياً من إيصال الاستلام')
        except Exception as exc:
            logger.warning('تعذّر الترحيل التلقائي لفاتورة %s المحوّلة من إيصال الاستلام: %s', invoice.invoice_number, exc)
            messages.warning(request, f'تم إنشاء الفاتورة {invoice.invoice_number} ولكنها تحتاج ترحيلاً يدوياً')

    return redirect('purchases:invoice_detail', pk=invoice.pk)
