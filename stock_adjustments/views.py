from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from .models import StockAdjustment, StockAdjustmentLine
from warehouses.models import Warehouse
from purchases.models import Product
from common.permissions import screen_permission_required
import logging

logger = logging.getLogger('accounting')


@screen_permission_required('stock_adjustments.adjustment', 'view')
def adjustment_list(request):
    adjustments = StockAdjustment.objects.select_related('warehouse', 'created_by').all()
    paginator = Paginator(adjustments, 25)
    page = request.GET.get('page')
    adjustments_page = paginator.get_page(page)
    return render(request, 'stock_adjustments/adjustment_list.html', {'adjustments': adjustments_page})


@screen_permission_required('stock_adjustments.adjustment', 'add')
def adjustment_create(request):
    warehouses = Warehouse.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        errors = []
        adjustment_number = request.POST.get('adjustment_number', '').strip()
        date_val = request.POST.get('date', '').strip()
        adjustment_type = request.POST.get('adjustment_type', '').strip()
        warehouse_id = request.POST.get('warehouse', '').strip()
        if not adjustment_number:
            errors.append('رقم الجرد مطلوب.')
        if not date_val:
            errors.append('تاريخ الجرد مطلوب.')
        if not adjustment_type:
            errors.append('نوع الجرد مطلوب.')
        if not warehouse_id:
            errors.append('المستودع مطلوب.')

        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        notes_list = request.POST.getlist('line_notes')
        parsed_lines = []
        for i, pid in enumerate(product_ids):
            if not pid:
                continue
            qty_raw = quantities[i] if i < len(quantities) else ''
            if not qty_raw or not qty_raw.strip():
                continue
            try:
                qty = Decimal(qty_raw)
            except (InvalidOperation, ValueError):
                errors.append(f'الكمية غير صالحة في البند رقم {i + 1}.')
                continue
            parsed_lines.append((pid, qty, notes_list[i] if i < len(notes_list) else ''))

        if errors:
            for e in errors:
                messages.error(request, e)
            next_number = f'ADJ-{timezone.now().strftime("%Y%m%d")}-{StockAdjustment.objects.count() + 1:04d}'
            return render(request, 'stock_adjustments/adjustment_form.html', {
                'warehouses': warehouses, 'products': products, 'next_number': next_number,
            })

        with transaction.atomic():
            adj = StockAdjustment.objects.create(
                adjustment_number=adjustment_number,
                date=date_val,
                adjustment_type=adjustment_type,
                warehouse_id=warehouse_id,
                reason=request.POST.get('reason', ''),
                notes=request.POST.get('notes', ''),
                created_by=request.user,
            )
            from warehouses.models import WarehouseProduct
            for pid, qty, note in parsed_lines:
                wp = WarehouseProduct.objects.filter(warehouse_id=warehouse_id, product_id=pid).first()
                current = wp.quantity if wp else 0
                StockAdjustmentLine.objects.create(
                    adjustment=adj,
                    product_id=pid,
                    quantity=qty,
                    current_stock=current,
                    notes=note,
                )
        messages.success(request, f'تم إنشاء جرد {adj.adjustment_number} بنجاح')
        return redirect('stock_adjustments:detail', pk=adj.pk)
    next_number = f'ADJ-{timezone.now().strftime("%Y%m%d")}-{StockAdjustment.objects.count() + 1:04d}'
    return render(request, 'stock_adjustments/adjustment_form.html', {
        'warehouses': warehouses, 'products': products, 'next_number': next_number,
    })


@screen_permission_required('stock_adjustments.adjustment', 'view')
def adjustment_detail(request, pk):
    adj = get_object_or_404(StockAdjustment, pk=pk)
    lines = adj.lines.select_related('product').all()
    return render(request, 'stock_adjustments/adjustment_detail.html', {'adjustment': adj, 'lines': lines})


@require_POST
@screen_permission_required('stock_adjustments.adjustment', 'edit')
def adjustment_approve(request, pk):
    adj = get_object_or_404(StockAdjustment, pk=pk)
    if adj.status == 'draft':
        try:
            adj.approve()
            messages.success(request, f'تم اعتماد وتنفيذ جرد {adj.adjustment_number}')
        except ValueError as e:
            messages.error(request, 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.')
            logger.exception('Posting failed for StockAdjustment %s', pk)
    return redirect('stock_adjustments:detail', pk=pk)


@require_POST
@screen_permission_required('stock_adjustments.adjustment', 'delete')
def adjustment_delete(request, pk):
    adj = get_object_or_404(StockAdjustment, pk=pk)
    if adj.status == 'draft':
        adj.delete()
        messages.success(request, 'تم حذف الجرد')
    return redirect('stock_adjustments:list')
