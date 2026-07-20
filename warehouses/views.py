from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, F, Count
from common.permissions import (
    screen_permission_required,
    filter_by_user_warehouses, visible_warehouse_ids, can_warehouse_operation,
)
from .models import Warehouse, WarehouseProduct, StockMovement
from .forms import WarehouseForm, WarehouseProductForm, StockMovementForm
from purchases.models import Product

_MOVEMENT_OPERATION = {
    'in': 'receive', 'return_in': 'receive',
    'out': 'issue', 'return_out': 'issue',
    'transfer': 'transfer', 'adjustment': 'count',
}


@screen_permission_required('warehouses.warehouse', 'view')
def warehouse_list(request):
    warehouses = Warehouse.objects.annotate(
        product_count=Count('products'),
        total_quantity=Sum('products__quantity'),
    )
    allowed = visible_warehouse_ids(request.user)
    if allowed is not None:
        warehouses = warehouses.filter(id__in=allowed)
    return render(request, 'warehouses/warehouse_list.html', {'warehouses': warehouses})


@screen_permission_required('warehouses.warehouse', 'add')
def warehouse_create(request):
    if request.method == 'POST':
        form = WarehouseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء المخزن بنجاح')
            return redirect('warehouses:warehouse_list')
    else:
        form = WarehouseForm()
    return render(request, 'warehouses/warehouse_form.html', {'form': form})


@screen_permission_required('warehouses.warehouse', 'edit')
def warehouse_edit(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    if request.method == 'POST':
        form = WarehouseForm(request.POST, instance=warehouse)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل المخزن بنجاح')
            return redirect('warehouses:warehouse_detail', pk=pk)
    else:
        form = WarehouseForm(instance=warehouse)
    return render(request, 'warehouses/warehouse_form.html', {'form': form, 'object': warehouse})


@screen_permission_required('warehouses.warehouse', 'view')
def warehouse_detail(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    allowed = visible_warehouse_ids(request.user)
    if allowed is not None and str(warehouse.pk) not in allowed:
        messages.error(request, 'ليس لديك صلاحية على هذا المخزن')
        return redirect('warehouses:warehouse_list')
    products = warehouse.products.select_related('product').all()
    movements = warehouse.movements.select_related('product', 'performed_by')[:20]
    low_stock = products.filter(quantity__lte=F('minimum_quantity')).exclude(minimum_quantity=0)
    return render(request, 'warehouses/warehouse_detail.html', {
        'warehouse': warehouse,
        'products': products,
        'movements': movements,
        'low_stock': low_stock,
    })


@screen_permission_required('warehouses.warehouse', 'add')
def warehouse_product_add(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    if not can_warehouse_operation(request.user, warehouse.pk, 'receive') \
            and visible_warehouse_ids(request.user) is not None:
        messages.error(request, 'ليس لديك صلاحية إضافة أصناف لهذا المخزن')
        return redirect('warehouses:warehouse_detail', pk=pk)
    if request.method == 'POST':
        form = WarehouseProductForm(request.POST)
        if form.is_valid():
            wp = form.save(commit=False)
            wp.warehouse = warehouse
            wp.save()
            messages.success(request, 'تم إضافة المنتج للمخزن بنجاح')
            return redirect('warehouses:warehouse_detail', pk=pk)
    else:
        form = WarehouseProductForm()
    return render(request, 'warehouses/warehouse_product_form.html', {
        'form': form, 'warehouse': warehouse
    })


@screen_permission_required('warehouses.stockmovement', 'view')
def movement_list(request):
    movements = StockMovement.objects.select_related('warehouse', 'to_warehouse', 'product', 'performed_by').all()
    movements = filter_by_user_warehouses(movements, request.user, field='warehouse')
    type_filter = request.GET.get('type', '')
    search = request.GET.get('q', '')
    if type_filter:
        movements = movements.filter(movement_type=type_filter)
    if search:
        movements = movements.filter(
            Q(movement_number__icontains=search) | Q(product__name__icontains=search)
        )
    return render(request, 'warehouses/movement_list.html', {
        'movements': movements,
        'current_type': type_filter,
        'search': search,
    })


@screen_permission_required('warehouses.stockmovement', 'add')
def movement_create(request):
    if request.method == 'POST':
        form = StockMovementForm(request.POST)
        if form.is_valid():
            from django.db import transaction as db_transaction
            from django.core.exceptions import ValidationError
            movement = form.save(commit=False)
            movement.performed_by = request.user
            movement.total_cost = movement.quantity * movement.unit_cost
            restricted = visible_warehouse_ids(request.user) is not None
            if restricted:
                operation = _MOVEMENT_OPERATION.get(movement.movement_type, 'issue')
                if not can_warehouse_operation(request.user, movement.warehouse_id, operation):
                    messages.error(request, 'ليس لديك صلاحية هذه العملية على المخزن المحدد')
                    return render(request, 'warehouses/movement_form.html', {'form': form})
                if movement.movement_type == 'transfer' and movement.to_warehouse_id and \
                        not can_warehouse_operation(request.user, movement.to_warehouse_id, 'receive'):
                    messages.error(request, 'ليس لديك صلاحية الاستلام في المخزن المستلِم')
                    return render(request, 'warehouses/movement_form.html', {'form': form})
            with db_transaction.atomic():
                wp, created = WarehouseProduct.objects.select_for_update().get_or_create(
                    warehouse=movement.warehouse, product=movement.product,
                    defaults={'quantity': 0}
                )
                if movement.movement_type in ('out', 'return_out', 'transfer'):
                    if wp.quantity < movement.quantity:
                        raise ValidationError(
                            f'مخزون غير كافٍ في {movement.warehouse.name}. '
                            f'المتوفر: {wp.quantity}، المطلوب: {movement.quantity}'
                        )
                if movement.movement_type in ('in', 'return_in'):
                    wp.quantity += movement.quantity
                elif movement.movement_type in ('out', 'return_out'):
                    wp.quantity -= movement.quantity
                elif movement.movement_type == 'transfer':
                    wp.quantity -= movement.quantity
                    if movement.to_warehouse:
                        wp2, _ = WarehouseProduct.objects.select_for_update().get_or_create(
                            warehouse=movement.to_warehouse, product=movement.product,
                            defaults={'quantity': 0}
                        )
                        wp2.quantity += movement.quantity
                        wp2.save(update_fields=['quantity'])
                elif movement.movement_type == 'adjustment':
                    wp.quantity = movement.quantity
                wp.save(update_fields=['quantity'])
                movement.save()
            messages.success(request, 'تم تسجيل حركة المخزون بنجاح')
            return redirect('warehouses:movement_detail', pk=movement.pk)
    else:
        form = StockMovementForm()
    return render(request, 'warehouses/movement_form.html', {'form': form})


@screen_permission_required('warehouses.stockmovement', 'view')
def movement_detail(request, pk):
    movement = get_object_or_404(
        StockMovement.objects.select_related('warehouse', 'to_warehouse', 'product', 'performed_by'), pk=pk)
    allowed = visible_warehouse_ids(request.user)
    if allowed is not None and str(movement.warehouse_id) not in allowed:
        messages.error(request, 'ليس لديك صلاحية على حركة هذا المخزن')
        return redirect('warehouses:movement_list')
    return render(request, 'warehouses/movement_detail.html', {'movement': movement})
