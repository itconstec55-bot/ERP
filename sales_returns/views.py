import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from common.permissions import screen_permission_required
from purchases.models import Product
from sales.models import Customer

from .models import SalesReturn, SalesReturnLine

logger = logging.getLogger('accounting')


@screen_permission_required('sales_returns.salesreturn', 'view')
def sales_return_list(request):
    returns = SalesReturn.objects.select_related('customer').all()
    paginator = Paginator(returns, 25)
    page = request.GET.get('page')
    returns_page = paginator.get_page(page)
    return render(request, 'sales_returns/return_list.html', {'returns': returns_page})


@screen_permission_required('sales_returns.salesreturn', 'add')
def sales_return_create(request):
    customers = Customer.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation

        errors = []
        return_number = request.POST.get('return_number', '').strip()
        date_val = request.POST.get('date', '').strip()
        customer_id = request.POST.get('customer', '').strip()
        if not return_number:
            errors.append('رقم المرتجع مطلوب.')
        if not date_val:
            errors.append('تاريخ المرتجع مطلوب.')
        if not customer_id:
            errors.append('العميل مطلوب.')

        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        prices = request.POST.getlist('unit_price')
        parsed_lines = []
        for i, pid in enumerate(product_ids):
            if not pid or i >= len(quantities) or i >= len(prices):
                continue
            qty_raw = quantities[i]
            price_raw = prices[i]
            if not qty_raw or not qty_raw.strip():
                continue
            try:
                qty = Decimal(qty_raw)
            except (InvalidOperation, ValueError):
                errors.append(f'الكمية غير صالحة في البند رقم {i + 1}.')
                continue
            if qty <= 0:
                errors.append(f'الكمية يجب أن تكون أكبر من صفر في البند رقم {i + 1}.')
                continue
            try:
                price = Decimal(price_raw or '0')
            except (InvalidOperation, ValueError):
                errors.append(f'سعر الوحدة غير صالح في البند رقم {i + 1}.')
                continue
            if price < 0:
                errors.append(f'سعر الوحدة لا يمكن أن يكون سالباً في البند رقم {i + 1}.')
                continue
            parsed_lines.append((pid, qty, price))

        if errors:
            for e in errors:
                messages.error(request, e)
            next_number = f'RET-S-{timezone.now().strftime("%Y%m%d")}-{SalesReturn.objects.count() + 1:04d}'
            return render(
                request,
                'sales_returns/return_form.html',
                {'customers': customers, 'products': products, 'next_number': next_number},
            )

        with transaction.atomic():
            sr = SalesReturn.objects.create(
                return_number=return_number,
                date=date_val,
                customer_id=customer_id,
                original_invoice_id=request.POST.get('original_invoice') or None,
                reason=request.POST.get('reason', ''),
                created_by=request.user,
            )
            for pid, qty, price in parsed_lines:
                SalesReturnLine.objects.create(sales_return=sr, product_id=pid, quantity=qty, unit_price=price)
            sr.calculate_totals()
        messages.success(request, f'تم إنشاء المرتجع {sr.return_number} بنجاح')
        return redirect('sales_returns:detail', pk=sr.pk)
    next_number = f'RET-S-{timezone.now().strftime("%Y%m%d")}-{SalesReturn.objects.count() + 1:04d}'
    return render(
        request,
        'sales_returns/return_form.html',
        {'customers': customers, 'products': products, 'next_number': next_number},
    )


@screen_permission_required('sales_returns.salesreturn', 'view')
def sales_return_detail(request, pk):
    sr = get_object_or_404(SalesReturn, pk=pk)
    lines = sr.lines.select_related('product').all()
    return render(request, 'sales_returns/return_detail.html', {'return_obj': sr, 'lines': lines})


@require_POST
@screen_permission_required('sales_returns.salesreturn', 'edit')
def sales_return_post(request, pk):
    sr = get_object_or_404(SalesReturn, pk=pk)
    try:
        sr.create_journal_entry()
        import uuid as _uuid
        from decimal import Decimal

        from warehouses.models import StockMovement, Warehouse, WarehouseProduct

        lines = sr.lines.select_related('product').all()
        for line in lines:
            if line.quantity <= 0:
                continue
            warehouse = Warehouse.objects.first()
            if not warehouse:
                continue
            StockMovement.objects.create(
                movement_number=f'SR-{sr.return_number}-{line.product.code}-{_uuid.uuid4().hex[:6]}',
                movement_type='in',
                warehouse=warehouse,
                product=line.product,
                quantity=line.quantity,
                unit_cost=line.unit_price,
                reference_number=sr.return_number,
                notes='إرجاع من مبيعات',
                date=sr.date,
                performed_by=request.user,
            )
            wp, _ = WarehouseProduct.objects.get_or_create(
                warehouse=warehouse, product=line.product, defaults={'quantity': Decimal('0')}
            )
            wp.quantity = (wp.quantity or Decimal('0')) + line.quantity
            wp.save(update_fields=['quantity'])
        messages.success(request, f'تم ترحيل المرتجع {sr.return_number} وتحديث المخزون بنجاح')
    except Exception:
        messages.error(request, 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.')
        logger.exception('Posting failed for SalesReturn %s', pk)
    return redirect('sales_returns:detail', pk=pk)


@require_POST
@screen_permission_required('sales_returns.salesreturn', 'delete')
def sales_return_delete(request, pk):
    sr = get_object_or_404(SalesReturn, pk=pk)
    if sr.is_posted:
        messages.error(request, 'لا يمكن حذف مرتجع مرحل — ألغِ الترحيل أولاً')
    else:
        sr.delete()
        messages.success(request, 'تم حذف المرتجع')
    return redirect('sales_returns:list')
