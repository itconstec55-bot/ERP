import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.models import SequenceNumber
from common.permissions import get_user_profile, screen_permission_required
from purchases.models import Product
from sales.models import Customer, SalesInvoice, SalesInvoiceLine

from .forms import SalesOrderForm, SalesOrderLineFormSet
from .models import SalesOrder

logger = logging.getLogger('accounting')


@screen_permission_required('sales_orders.salesorder', 'view')
def so_list(request):
    orders = SalesOrder.objects.select_related('customer', 'created_by').all()
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
    customer_id = request.GET.get('customer')
    if customer_id:
        orders = orders.filter(customer_id=customer_id)
    paginator = Paginator(orders, 25)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    return render(
        request,
        'sales_orders/so_list.html',
        {'orders': orders_page, 'status_filter': status, 'customers': Customer.objects.filter(is_active=True)},
    )


@screen_permission_required('sales_orders.salesorder', 'add')
def so_create(request):
    if request.method == 'POST':
        form = SalesOrderForm(request.POST)
        formset = SalesOrderLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.created_by = request.user
                order.save()
                formset.instance = order
                formset.save()
            messages.success(request, 'تم إنشاء أمر البيع بنجاح')
            return redirect('sales_orders:so_detail', pk=order.pk)
    else:
        form = SalesOrderForm()
        formset = SalesOrderLineFormSet()
    products = Product.objects.filter(is_active=True)
    return render(
        request,
        'sales_orders/so_form.html',
        {'form': form, 'formset': formset, 'products': products, 'title': 'إنشاء أمر بيع جديد'},
    )


@screen_permission_required('sales_orders.salesorder', 'view')
def so_detail(request, pk):
    order = get_object_or_404(SalesOrder.objects.select_related('customer'), pk=pk)
    lines = order.lines.select_related('product').all()
    return render(request, 'sales_orders/so_detail.html', {'order': order, 'lines': lines})


@screen_permission_required('sales_orders.salesorder', 'edit')
def so_edit(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if order.status in ('invoiced', 'cancelled'):
        messages.error(request, 'لا يمكن تعديل أمر بيع مفوتر أو ملغي')
        return redirect('sales_orders:so_detail', pk=order.pk)
    if request.method == 'POST':
        form = SalesOrderForm(request.POST, instance=order)
        formset = SalesOrderLineFormSet(request.POST, instance=order)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, 'تم تعديل أمر البيع بنجاح')
            return redirect('sales_orders:so_detail', pk=order.pk)
    else:
        form = SalesOrderForm(instance=order)
        formset = SalesOrderLineFormSet(instance=order)
    products = Product.objects.filter(is_active=True)
    return render(
        request,
        'sales_orders/so_form.html',
        {
            'form': form,
            'formset': formset,
            'products': products,
            'order': order,
            'title': f'تعديل أمر البيع {order.order_number}',
        },
    )


@require_POST
@screen_permission_required('sales_orders.salesorder', 'edit')
def so_confirm(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if order.status in ('cancelled', 'invoiced'):
        messages.error(request, 'لا يمكن تأكيد أمر بيع ملغي أو مفوتر')
    else:
        order.status = 'confirmed'
        order.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'تم تأكيد أمر البيع {order.order_number}')
    return redirect('sales_orders:so_detail', pk=order.pk)


@require_POST
@screen_permission_required('sales_orders.salesorder', 'edit')
def so_cancel(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if order.status == 'invoiced':
        messages.error(request, 'لا يمكن إلغاء أمر بيع مفوتر')
    else:
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'تم إلغاء أمر البيع {order.order_number}')
    return redirect('sales_orders:so_detail', pk=order.pk)


@require_POST
@screen_permission_required('sales_orders.salesorder', 'edit')
def so_to_invoice(request, pk):
    order = get_object_or_404(SalesOrder.objects.select_related('customer'), pk=pk)
    if order.status == 'cancelled':
        messages.error(request, 'لا يمكن تحويل أمر بيع ملغي إلى فاتورة')
        return redirect('sales_orders:so_detail', pk=order.pk)

    with transaction.atomic():
        invoice = SalesInvoice.objects.create(
            invoice_number=SequenceNumber.get_next_number('sales_invoice'),
            customer=order.customer,
            date=order.date,
            notes=f'محوَّلة من أمر البيع {order.order_number}\n' + (order.notes or ''),
            created_by=request.user,
        )
        profile = get_user_profile(request.user)
        if profile and profile.branch:
            invoice.branch = profile.branch
        invoice.save(update_fields=['branch'])
        created = 0
        for line in order.lines.select_related('product').all():
            remaining = line.quantity - line.invoiced_quantity
            if remaining <= 0:
                continue
            SalesInvoiceLine.objects.create(
                invoice=invoice,
                product=line.product,
                quantity=remaining,
                unit_price=line.unit_price,
                cost_price=line.product.purchase_price,
                discount_percent=0,
            )
            created += 1
        if created == 0:
            invoice.delete()
            messages.warning(request, 'لا توجد بنود قابلة للتحويل (تم ترحيل الكميات بالكامل)')
            return redirect('sales_orders:so_detail', pk=order.pk)
        invoice.calculate_totals()
        order.status = 'invoiced'
        order.save(update_fields=['status', 'updated_at'])

    messages.success(request, f'تم إنشاء فاتورة المبيعات {invoice.invoice_number} من أمر البيع')
    return redirect('sales:invoice_detail', pk=invoice.pk)
