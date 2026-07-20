from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from common.permissions import object_permission_required, screen_permission_required

from .forms import (
    BatchStatusUpdateForm,
    ConcreteMixDesignForm,
    CustomerRequestForm,
    DeliveryScheduleForm,
    MixComponentFormSet,
    ProductionBatchForm,
    ProductionCostForm,
    ProductionOrderFilterForm,
    ProductionOrderForm,
    SiloForm,
    SiloTransactionForm,
    TruckForm,
)
from .models import (
    ConcreteMixDesign,
    CustomerRequest,
    DeliverySchedule,
    ProductionBatch,
    ProductionCost,
    ProductionOrder,
    Silo,
    SiloTransaction,
    Truck,
)

# ══════════════════════════════════════════════════════════════
# لوحة التحكم الرئيسية
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def dashboard(request):
    today = timezone.now().date()
    context = {
        'total_orders': ProductionOrder.objects.count(),
        'active_orders': ProductionOrder.objects.filter(status__in=['draft', 'scheduled', 'in_progress']).count(),
        'today_deliveries': DeliverySchedule.objects.filter(delivery_date=today).count(),
        'available_trucks': Truck.objects.filter(status='available', is_active=True).count(),
        'total_trucks': Truck.objects.filter(is_active=True).count(),
        'pending_batches': ProductionBatch.objects.filter(status__in=['queued', 'mixing', 'loading']).count(),
        'mix_designs_count': ConcreteMixDesign.objects.filter(is_active=True).count(),
        'recent_orders': ProductionOrder.objects.select_related('customer_request__customer', 'mix_design')[:10],
        'today_schedule': DeliverySchedule.objects.filter(delivery_date=today).select_related(
            'production_order__customer_request__customer', 'truck'
        )[:10],
    }
    return render(request, 'concrete_production/dashboard.html', context)


# ══════════════════════════════════════════════════════════════
# تصاميم الخلطات
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def mix_design_list(request):
    mixes = ConcreteMixDesign.objects.all()
    search = request.GET.get('search', '')
    if search:
        mixes = mixes.filter(Q(code__icontains=search) | Q(name__icontains=search))
    paginator = Paginator(mixes, 25)
    page = request.GET.get('page')
    mixes_page = paginator.get_page(page)
    return render(request, 'concrete_production/mix_design_list.html', {'mixes': mixes_page, 'search': search})


@screen_permission_required('concrete_production.production', 'add')
def mix_design_create(request):
    if request.method == 'POST':
        form = ConcreteMixDesignForm(request.POST)
        formset = MixComponentFormSet(request.POST, prefix='components')
        if form.is_valid() and formset.is_valid():
            mix = form.save()
            formset.instance = mix
            formset.save()
            mix.calculate_cost()
            messages.success(request, 'تم إنشاء تصميم الخلطة بنجاح')
            return redirect('concrete_production:mix_design_detail', pk=mix.pk)
    else:
        form = ConcreteMixDesignForm()
        formset = MixComponentFormSet(prefix='components')
    return render(
        request,
        'concrete_production/mix_design_form.html',
        {'form': form, 'formset': formset, 'title': 'إضافة تصميم خلطة جديد'},
    )


@screen_permission_required('concrete_production.production', 'view')
def mix_design_detail(request, pk):
    mix = get_object_or_404(ConcreteMixDesign, pk=pk)
    components = mix.components.all()
    return render(request, 'concrete_production/mix_design_detail.html', {'mix': mix, 'components': components})


@screen_permission_required('concrete_production.production', 'edit')
def mix_design_edit(request, pk):
    mix = get_object_or_404(ConcreteMixDesign, pk=pk)
    if request.method == 'POST':
        form = ConcreteMixDesignForm(request.POST, instance=mix)
        formset = MixComponentFormSet(request.POST, instance=mix, prefix='components')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            mix.calculate_cost()
            messages.success(request, 'تم تحديث تصميم الخلطة بنجاح')
            return redirect('concrete_production:mix_design_detail', pk=mix.pk)
    else:
        form = ConcreteMixDesignForm(instance=mix)
        formset = MixComponentFormSet(instance=mix, prefix='components')
    return render(
        request,
        'concrete_production/mix_design_form.html',
        {'form': form, 'formset': formset, 'mix': mix, 'title': 'تعديل تصميم الخلطة'},
    )


# ══════════════════════════════════════════════════════════════
# طلبات العملاء
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def customer_request_list(request):
    requests_list = CustomerRequest.objects.select_related('customer')
    status = request.GET.get('status', '')
    if status:
        requests_list = requests_list.filter(status=status)
    paginator = Paginator(requests_list, 25)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)
    return render(
        request, 'concrete_production/customer_request_list.html', {'requests': requests_page, 'status': status}
    )


@screen_permission_required('concrete_production.production', 'add')
def customer_request_create(request):
    if request.method == 'POST':
        form = CustomerRequestForm(request.POST)
        if form.is_valid():
            cr = form.save(commit=False)
            cr.created_by = request.user
            cr.save()
            messages.success(request, f'تم إنشاء الطلب {cr.request_number} بنجاح')
            return redirect('concrete_production:customer_request_detail', pk=cr.pk)
    else:
        form = CustomerRequestForm()
    return render(request, 'concrete_production/customer_request_form.html', {'form': form, 'title': 'طلب عميل جديد'})


@screen_permission_required('concrete_production.production', 'view')
def customer_request_detail(request, pk):
    cr = get_object_or_404(CustomerRequest, pk=pk)
    orders = cr.production_orders.select_related('mix_design')
    return render(request, 'concrete_production/customer_request_detail.html', {'request_obj': cr, 'orders': orders})


@screen_permission_required('concrete_production.production', 'edit')
def customer_request_confirm(request, pk):
    cr = get_object_or_404(CustomerRequest, pk=pk)
    if request.method == 'POST':
        cr.status = 'confirmed'
        cr.save(update_fields=['status'])
        messages.success(request, f'تم تأكيد الطلب {cr.request_number}')
    return redirect('concrete_production:customer_request_detail', pk=cr.pk)


# ══════════════════════════════════════════════════════════════
# أوامر الإنتاج
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def production_cost_per_m3(request):
    """تكلفة المتر المكعب لكل أمر إنتاج: مواد + تكاليف تشغيل."""
    orders = (
        ProductionOrder.objects.select_related('customer_request__customer', 'mix_design')
        .prefetch_related('costs')
        .all()
        .order_by('-created_at')
    )

    rows = []
    grand_qty = grand_material = grand_other = grand_total = Decimal('0')
    for po in orders:
        material_cost = po.mix_design.cost_per_m3 * po.quantity_m3
        other_cost = sum((c.amount for c in po.costs.all()), Decimal('0'))
        total_cost = material_cost + other_cost
        cost_per_m3 = (total_cost / po.quantity_m3) if po.quantity_m3 else Decimal('0')
        profit_per_m3 = po.unit_price - cost_per_m3
        margin = (profit_per_m3 / po.unit_price * 100) if po.unit_price else Decimal('0')
        rows.append(
            {
                'po': po,
                'material_cost': material_cost,
                'other_cost': other_cost,
                'total_cost': total_cost,
                'cost_per_m3': cost_per_m3,
                'selling_per_m3': po.unit_price,
                'profit_per_m3': profit_per_m3,
                'margin': margin,
            }
        )
        grand_qty += po.quantity_m3
        grand_material += material_cost
        grand_other += other_cost
        grand_total += total_cost

    grand_cost_per_m3 = (grand_total / grand_qty) if grand_qty else Decimal('0')

    return render(
        request,
        'concrete_production/production_cost_per_m3.html',
        {
            'rows': rows,
            'grand_qty': grand_qty,
            'grand_material': grand_material,
            'grand_other': grand_other,
            'grand_total': grand_total,
            'grand_cost_per_m3': grand_cost_per_m3,
        },
    )


@screen_permission_required('concrete_production.production', 'view')
def production_order_list(request):
    from common.permissions import filter_by_branch

    orders = filter_by_branch(
        ProductionOrder.objects.select_related('customer_request__customer', 'mix_design'), request.user
    )
    filter_form = ProductionOrderFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            orders = orders.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('priority'):
            orders = orders.filter(priority=filter_form.cleaned_data['priority'])
        if filter_form.cleaned_data.get('date_from'):
            orders = orders.filter(created_at__date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            orders = orders.filter(created_at__date__lte=filter_form.cleaned_data['date_to'])
    paginator = Paginator(orders, 25)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    return render(
        request, 'concrete_production/production_order_list.html', {'orders': orders_page, 'filter_form': filter_form}
    )


@screen_permission_required('concrete_production.production', 'add')
def production_order_create(request):
    if request.method == 'POST':
        form = ProductionOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            from common.permissions import get_user_profile

            profile = get_user_profile(request.user)
            if profile and profile.branch:
                order.branch = profile.branch
            order.save()
            messages.success(request, f'تم إنشاء أمر الإنتاج {order.order_number} بنجاح')
            return redirect('concrete_production:production_order_detail', pk=order.pk)
    else:
        form = ProductionOrderForm()
    return render(request, 'concrete_production/production_order_form.html', {'form': form, 'title': 'أمر إنتاج جديد'})


@object_permission_required('concrete_production.view_productionorder', model=ProductionOrder)
@screen_permission_required('concrete_production.production', 'view')
def production_order_detail(request, pk):
    order = get_object_or_404(ProductionOrder.objects.select_related('customer_request__customer', 'mix_design'), pk=pk)
    batches = order.batches.select_related('truck')
    deliveries = order.delivery_schedules.select_related('truck')
    costs = order.costs.all()
    components = order.mix_design.components.all()
    return render(
        request,
        'concrete_production/production_order_detail.html',
        {'order': order, 'batches': batches, 'deliveries': deliveries, 'costs': costs, 'components': components},
    )


@screen_permission_required('concrete_production.production', 'edit')
def production_order_schedule(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)
    if request.method == 'POST':
        form = ProductionOrderForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save()
            if order.status == 'draft':
                order.status = 'scheduled'
                order.save(update_fields=['status'])
            messages.success(request, 'تم تحديث جدولة أمر الإنتاج')
            return redirect('concrete_production:production_order_detail', pk=order.pk)
    else:
        form = ProductionOrderForm(instance=order)
    return render(
        request,
        'concrete_production/production_order_form.html',
        {'form': form, 'order': order, 'title': 'جدولة أمر الإنتاج'},
    )


# ══════════════════════════════════════════════════════════════
# الدفعات الإنتاجية
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def batch_list(request):
    batches = ProductionBatch.objects.select_related('production_order__customer_request__customer', 'truck')
    status = request.GET.get('status', '')
    if status:
        batches = batches.filter(status=status)
    paginator = Paginator(batches, 25)
    page = request.GET.get('page')
    batches_page = paginator.get_page(page)
    return render(request, 'concrete_production/batch_list.html', {'batches': batches_page, 'status': status})


@screen_permission_required('concrete_production.production', 'view')
def production_daily(request):
    """شاشة متابعة أوامر الإنتاج اليومية - تجمع الأوامر المجدولة اليوم مع حالة دفعاتها وتوقع التسليم"""
    today = timezone.now().date()
    selected_date = request.GET.get('date')
    if selected_date:
        try:
            from datetime import datetime

            today = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    weekday = today.weekday()

    orders = (
        ProductionOrder.objects.filter(scheduled_date=today)
        .select_related('customer_request__customer', 'mix_design')
        .prefetch_related('batches')
        .order_by('scheduled_time_from')
    )

    total_orders = orders.count()
    total_quantity = float(orders.aggregate(t=Sum('quantity_m3'))['t'] or 0)
    produced_quantity = float(
        ProductionBatch.objects.filter(production_order__in=orders, status='completed').aggregate(
            t=Sum('actual_quantity_m3')
        )['t']
        or 0
    )

    order_data = []
    for order in orders:
        batches = list(order.batches.all())
        completed_batches = [b for b in batches if b.status == 'completed']
        status_label = (
            'completed'
            if order.status == 'completed'
            else ('in_progress' if order.status == 'in_progress' else 'pending')
        )
        order_data.append(
            {
                'order': order,
                'batches': batches,
                'batch_count': len(batches),
                'completed_count': len(completed_batches),
                'produced': float(sum((b.actual_quantity_m3 or 0) for b in completed_batches)),
                'remaining': float(
                    max(order.quantity_m3 - sum((b.actual_quantity_m3 or 0) for b in completed_batches), 0)
                ),
                'progress': float(
                    (sum((b.actual_quantity_m3 or 0) for b in completed_batches) / order.quantity_m3 * 100)
                    if order.quantity_m3
                    else 0
                ),
                'status_label': status_label,
            }
        )

    return render(
        request,
        'concrete_production/production_daily.html',
        {
            'selected_date': today,
            'orders': order_data,
            'total_orders': total_orders,
            'total_quantity': total_quantity,
            'produced_quantity': produced_quantity,
            'remaining_quantity': total_quantity - produced_quantity,
        },
    )


@screen_permission_required('concrete_production.production', 'add')
def batch_create(request):
    if request.method == 'POST':
        form = ProductionBatchForm(request.POST)
        if form.is_valid():
            batch = form.save()
            messages.success(request, f'تم إنشاء الدفعة {batch.batch_number} بنجاح')
            return redirect('concrete_production:batch_detail', pk=batch.pk)
    else:
        form = ProductionBatchForm()
    return render(request, 'concrete_production/batch_form.html', {'form': form, 'title': 'دفعة إنتاجية جديدة'})


@screen_permission_required('concrete_production.production', 'view')
def batch_detail(request, pk):
    batch = get_object_or_404(
        ProductionBatch.objects.select_related('production_order__customer_request__customer', 'truck'), pk=pk
    )
    status_form = BatchStatusUpdateForm()
    return render(request, 'concrete_production/batch_detail.html', {'batch': batch, 'status_form': status_form})


@screen_permission_required('concrete_production.production', 'edit')
def batch_update_status(request, pk):
    batch = get_object_or_404(ProductionBatch, pk=pk)
    if request.method == 'POST':
        form = BatchStatusUpdateForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            batch.status = new_status

            now = timezone.now()
            if new_status == 'mixing':
                batch.mixing_time = now
            elif new_status == 'in_transit':
                batch.departure_time = now
            elif new_status == 'pouring':
                batch.pouring_start = now
            elif new_status == 'completed':
                batch.pouring_end = now
                if form.cleaned_data.get('actual_quantity_m3'):
                    batch.actual_quantity_m3 = form.cleaned_data['actual_quantity_m3']
                if form.cleaned_data.get('returned_quantity_m3'):
                    batch.returned_quantity_m3 = form.cleaned_data['returned_quantity_m3']
                # تحديث الكمية المسلمة في أمر الإنتاج
                order = batch.production_order
                order.quantity_delivered += batch.actual_quantity_m3 - batch.returned_quantity_m3
                if order.quantity_delivered >= order.quantity_m3:
                    order.status = 'completed'
                order.save()
                # تحديث حالة الشاحنة
                if batch.truck:
                    batch.truck.status = 'available'
                    batch.truck.save(update_fields=['status'])

            elif new_status == 'in_transit':
                if batch.truck:
                    batch.truck.status = 'on_route'
                    batch.truck.save(update_fields=['status'])

            if form.cleaned_data.get('notes'):
                batch.notes = form.cleaned_data['notes']

            batch.save()
            messages.success(request, f'تم تحديث حالة الدفعة إلى {batch.get_status_display()}')
    return redirect('concrete_production:batch_detail', pk=pk)


# ══════════════════════════════════════════════════════════════
# الشاحنات
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def truck_list(request):
    trucks = Truck.objects.all()
    status = request.GET.get('status', '')
    if status:
        trucks = trucks.filter(status=status)
    return render(request, 'concrete_production/truck_list.html', {'trucks': trucks, 'status': status})


@screen_permission_required('concrete_production.production', 'add')
def truck_create(request):
    if request.method == 'POST':
        form = TruckForm(request.POST)
        if form.is_valid():
            truck = form.save()
            messages.success(request, f'تم إضافة الشاحنة {truck.plate_number} بنجاح')
            return redirect('concrete_production:truck_list')
    else:
        form = TruckForm()
    return render(request, 'concrete_production/truck_form.html', {'form': form, 'title': 'شاحنة جديدة'})


@screen_permission_required('concrete_production.production', 'edit')
def truck_edit(request, pk):
    truck = get_object_or_404(Truck, pk=pk)
    if request.method == 'POST':
        form = TruckForm(request.POST, instance=truck)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات الشاحنة')
            return redirect('concrete_production:truck_list')
    else:
        form = TruckForm(instance=truck)
    return render(
        request, 'concrete_production/truck_form.html', {'form': form, 'truck': truck, 'title': 'تعديل الشاحنة'}
    )


# ══════════════════════════════════════════════════════════════
# جدول التسليمات
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def delivery_list(request):
    deliveries = DeliverySchedule.objects.select_related(
        'production_order__customer_request__customer', 'truck', 'batch'
    )
    date = request.GET.get('date', '')
    if date:
        deliveries = deliveries.filter(delivery_date=date)
    else:
        deliveries = deliveries.filter(delivery_date__gte=timezone.now().date())
    paginator = Paginator(deliveries, 25)
    page = request.GET.get('page')
    deliveries_page = paginator.get_page(page)
    return render(request, 'concrete_production/delivery_list.html', {'deliveries': deliveries_page, 'date': date})


@screen_permission_required('concrete_production.production', 'add')
def delivery_create(request):
    if request.method == 'POST':
        form = DeliveryScheduleForm(request.POST)
        if form.is_valid():
            try:
                delivery = form.save()
                messages.success(request, 'تم إضافة جدول التسليم بنجاح')
                return redirect('concrete_production:delivery_list')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = DeliveryScheduleForm()
    return render(request, 'concrete_production/delivery_form.html', {'form': form, 'title': 'جدول تسليم جديد'})


# ══════════════════════════════════════════════════════════════
# تكاليف الإنتاج
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def cost_list(request):
    costs = ProductionCost.objects.select_related('production_order')
    order_pk = request.GET.get('order', '')
    if order_pk:
        costs = costs.filter(production_order_id=order_pk)
    paginator = Paginator(costs, 25)
    page = request.GET.get('page')
    costs_page = paginator.get_page(page)
    return render(request, 'concrete_production/cost_list.html', {'costs': costs_page, 'order_pk': order_pk})


@screen_permission_required('concrete_production.production', 'add')
def cost_create(request):
    if request.method == 'POST':
        form = ProductionCostForm(request.POST)
        if form.is_valid():
            cost = form.save()
            messages.success(request, 'تم إضافة التكلفة بنجاح')
            return redirect('concrete_production:cost_list')
    else:
        form = ProductionCostForm()
        order_pk = request.GET.get('order', '')
        if order_pk:
            form.fields['production_order'].initial = order_pk
    return render(request, 'concrete_production/cost_form.html', {'form': form, 'title': 'تكلفة جديدة'})


# ══════════════════════════════════════════════════════════════
# API endpoints
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def api_mix_components(request, pk):
    """API: مكونات الخلطة للعرض في نموذج أمر الإنتاج"""
    mix = get_object_or_404(ConcreteMixDesign, pk=pk)
    components = list(mix.components.values('name', 'quantity_kg', 'component_type'))
    return JsonResponse({'components': components, 'total_weight': float(mix.total_weight_per_m3)})


@screen_permission_required('concrete_production.production', 'view')
def api_available_trucks(request):
    """API: الشاحنات المتاحة"""
    trucks = Truck.objects.filter(status='available', is_active=True).values(
        'id', 'plate_number', 'driver_name', 'capacity_m3'
    )
    return JsonResponse({'trucks': list(trucks)})


@screen_permission_required('concrete_production.production', 'view')
def api_production_stats(request):
    """API: إحصائيات الإنتاج"""
    today = timezone.now().date()
    stats = {
        'today_batches': ProductionBatch.objects.filter(created_at__date=today).count(),
        'today_volume': float(
            ProductionBatch.objects.filter(created_at__date=today, status='completed').aggregate(
                total=Sum('actual_quantity_m3')
            )['total']
            or 0
        ),
        'active_orders': ProductionOrder.objects.filter(status__in=['scheduled', 'in_progress']).count(),
        'pending_deliveries': DeliverySchedule.objects.filter(
            delivery_date=today, status__in=['scheduled', 'confirmed']
        ).count(),
    }
    return JsonResponse(stats)


# ══════════════════════════════════════════════════════════════
# سيلو
# ══════════════════════════════════════════════════════════════


@screen_permission_required('concrete_production.production', 'view')
def silo_dashboard(request):
    silos = Silo.objects.filter(is_active=True)
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # Batch aggregate for all silos — avoids N+1 per silo
    monthly_totals = (
        SiloTransaction.objects.filter(date__date__gte=month_start)
        .values('silo_id', 'transaction_type')
        .annotate(total=Sum('quantity_tons'))
    )
    monthly_by_silo = {}
    for row in monthly_totals:
        sid = row['silo_id']
        if sid not in monthly_by_silo:
            monthly_by_silo[sid] = {'in': 0, 'out': 0}
        monthly_by_silo[sid][row['transaction_type']] = float(row['total'] or 0)

    silos_data = []
    for silo in silos:
        m = monthly_by_silo.get(silo.id, {'in': 0, 'out': 0})
        silos_data.append({'silo': silo, 'recent_in': m['in'], 'recent_out': m['out']})

    alerts = [s for s in silos if s.needs_reorder]

    agg = silos.aggregate(total_stock=Sum('current_stock_tons'), total_capacity=Sum('capacity_tons'))
    total_stock = float(agg['total_stock'] or 0)
    total_capacity = float(agg['total_capacity'] or 0)

    chart_data = {
        'names': [s.name for s in silos],
        'current': [float(s.current_stock_tons) for s in silos],
        'capacity': [float(s.capacity_tons) for s in silos],
        'minimum': [float(s.minimum_order_tons) for s in silos],
    }

    # Daily chart — single batch query instead of O(days × silos)
    daily_labels = []
    daily_totals = []
    if silos.exists():
        day_count = min(today.day, 30)
        daily_labels = [str(i) for i in range(day_count, 0, -1)]

        # Fetch ALL transactions for the month in one query
        all_tx = SiloTransaction.objects.filter(date__date__gte=month_start).values(
            'silo_id', 'transaction_type', 'date__date', 'quantity_tons'
        )

        # Build silo opening balances lookup
        silo_map = {s.id: float(s.current_stock_tons) for s in silos}

        # Pre-index transactions by (silo_id, date)
        from collections import defaultdict

        tx_by_silo_day = defaultdict(lambda: {'in': 0.0, 'out': 0.0})
        for tx in all_tx:
            key = (tx['silo_id'], tx['date__date'])
            val = float(tx['quantity_tons'] or 0)
            if tx['transaction_type'] == 'in':
                tx_by_silo_day[key] = tx_by_silo_day[key]
                tx_by_silo_day[key]['in'] += val
            else:
                tx_by_silo_day[key] = tx_by_silo_day[key]
                tx_by_silo_day[key]['out'] += val

        # Compute running cumulative per day
        cumulative = {sid: bal for sid, bal in silo_map.items()}
        for i in range(day_count, 0, -1):
            d = today.replace(day=i)
            day_total = 0.0
            for silo in silos:
                key = (silo.id, d)
                tx = tx_by_silo_day.get(key, {'in': 0.0, 'out': 0.0})
                net = tx['in'] - tx['out']
                cumulative[silo.id] -= net
                day_total += max(0, cumulative[silo.id])
            daily_totals.append(round(day_total, 1))
        chart_data['daily_labels'] = daily_labels
        chart_data['daily_totals'] = daily_totals
    else:
        chart_data['daily_labels'] = []
        chart_data['daily_totals'] = []

    recent_transactions = SiloTransaction.objects.select_related('silo', 'created_by')[:15]

    return render(
        request,
        'concrete_production/silo_dashboard.html',
        {
            'silos': silos,
            'silos_data': silos_data,
            'alerts': alerts,
            'total_stock': total_stock,
            'total_capacity': total_capacity,
            'chart_data_json': chart_data,
            'recent_transactions': recent_transactions,
        },
    )


@screen_permission_required('concrete_production.production', 'view')
def cement_daily_inventory(request):
    """جرد الأسمنت اليومي لكل سيلة: بداية، وارد، منصرف، نهاية."""
    from datetime import datetime

    selected = request.GET.get('date')
    if selected:
        try:
            d = datetime.strptime(selected, '%Y-%m-%d').date()
        except ValueError:
            d = timezone.now().date()
    else:
        d = timezone.now().date()

    silos = Silo.objects.filter(is_active=True)
    # تجميع واحد لكل السيلو/اليوم بدل استعلام لكل سيلة (تجنب N+1)
    agg = (
        SiloTransaction.objects.filter(date__date=d)
        .values('silo', 'transaction_type')
        .annotate(total=Coalesce(Sum('quantity_tons'), Value(Decimal('0'))))
    )
    flow = {}
    for row in agg:
        flow.setdefault(row['silo'], {'in': Decimal('0'), 'out': Decimal('0')})
        if row['transaction_type'] == 'in':
            flow[row['silo']]['in'] = row['total']
        elif row['transaction_type'] == 'out':
            flow[row['silo']]['out'] = row['total']
    # جلب حركات اليوم دفعة واحدة لعرضها مجمّعة حسب السيلة
    day_txns = list(
        SiloTransaction.objects.filter(date__date=d).select_related('silo', 'production_order', 'created_by')
    )
    txns_by_silo = {}
    for t in day_txns:
        txns_by_silo.setdefault(t.silo_id, []).append(t)

    rows = []
    total_open = total_in = total_out = total_close = Decimal('0')
    for silo in silos:
        f = flow.get(silo.pk, {'in': Decimal('0'), 'out': Decimal('0')})
        in_qty = f['in']
        out_qty = f['out']
        close = silo.current_stock_tons
        open_stock = close - in_qty + out_qty
        rows.append(
            {
                'silo': silo,
                'opening': open_stock,
                'incoming': in_qty,
                'outgoing': out_qty,
                'closing': close,
                'transactions': txns_by_silo.get(silo.pk, []),
            }
        )
        total_open += open_stock
        total_in += in_qty
        total_out += out_qty
        total_close += close

    return render(
        request,
        'concrete_production/cement_daily_inventory.html',
        {
            'selected_date': d,
            'rows': rows,
            'total_open': total_open,
            'total_in': total_in,
            'total_out': total_out,
            'total_close': total_close,
            'today': timezone.now().date(),
        },
    )


@screen_permission_required('concrete_production.production', 'view')
def silo_list(request):
    silos = Silo.objects.filter(is_active=True)
    return render(request, 'concrete_production/silo_list.html', {'silos': silos})


@screen_permission_required('concrete_production.production', 'view')
def silo_detail(request, pk):
    silo = get_object_or_404(Silo, pk=pk)
    transactions = SiloTransaction.objects.filter(silo=silo).select_related('created_by')[:30]

    month_start = timezone.now().date().replace(day=1)
    monthly_stats = (
        SiloTransaction.objects.filter(silo=silo, date__date__gte=month_start)
        .values('transaction_type')
        .annotate(total_qty=Sum('quantity_tons'), count=Count('id'))
    )

    return render(
        request,
        'concrete_production/silo_detail.html',
        {'silo': silo, 'transactions': transactions, 'monthly_stats': monthly_stats},
    )


@screen_permission_required('concrete_production.production', 'add')
def silo_create(request):
    if request.method == 'POST':
        form = SiloForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء السيلة بنجاح')
            return redirect('concrete_production:silo_list')
    else:
        form = SiloForm()
    return render(request, 'concrete_production/silo_form.html', {'form': form, 'title': 'سيلة جديدة'})


@screen_permission_required('concrete_production.production', 'edit')
def silo_edit(request, pk):
    silo = get_object_or_404(Silo, pk=pk)
    if request.method == 'POST':
        form = SiloForm(request.POST, instance=silo)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل السيلة بنجاح')
            return redirect('concrete_production:silo_detail', pk=silo.pk)
    else:
        form = SiloForm(instance=silo)
    return render(request, 'concrete_production/silo_form.html', {'form': form, 'title': 'تعديل السيلة', 'silo': silo})


@screen_permission_required('concrete_production.production', 'add')
def silo_transaction_create(request, silo_pk):
    silo = get_object_or_404(Silo, pk=silo_pk)
    if request.method == 'POST':
        form = SiloTransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.silo = silo
            txn.created_by = request.user
            txn.save()
            messages.success(request, 'تم تسجيل الحركة بنجاح')
            return redirect('concrete_production:silo_detail', pk=silo.pk)
    else:
        form = SiloTransactionForm(initial={'silo': silo})
    return render(request, 'concrete_production/silo_transaction_form.html', {'form': form, 'silo': silo})


@screen_permission_required('concrete_production.production', 'view')
def api_silo_stock(request):
    """API: بيانات المخزون للرسم البياني"""
    silos = Silo.objects.filter(is_active=True)
    data = {
        'names': [s.name for s in silos],
        'current': [float(s.current_stock_tons) for s in silos],
        'capacity': [float(s.capacity_tons) for s in silos],
        'minimum': [float(s.minimum_order_tons) for s in silos],
        'critical': [float(s.critical_level_tons) for s in silos],
        'percentages': [s.fill_percentage for s in silos],
        'statuses': [s.status for s in silos],
    }
    return JsonResponse(data)
