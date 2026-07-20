from django.contrib import admin

from .models import (
    ConcreteMixDesign,
    CustomerRequest,
    DeliverySchedule,
    MixComponent,
    ProductionBatch,
    ProductionCost,
    ProductionOrder,
    Silo,
    SiloTransaction,
    Truck,
)


class MixComponentInline(admin.TabularInline):
    model = MixComponent
    extra = 3
    fields = ['component_type', 'name', 'quantity_kg', 'product', 'order']


@admin.register(ConcreteMixDesign)
class ConcreteMixDesignAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'name',
        'strength_class',
        'slump_cm',
        'target_strength_mpa',
        'selling_price_per_m3',
        'is_active',
    ]
    list_filter = ['is_active', 'strength_class']
    search_fields = ['code', 'name']
    inlines = [MixComponentInline]


@admin.register(MixComponent)
class MixComponentAdmin(admin.ModelAdmin):
    list_display = ['mix_design', 'component_type', 'name', 'quantity_kg', 'product']
    list_filter = ['component_type']
    search_fields = ['name']


@admin.register(CustomerRequest)
class CustomerRequestAdmin(admin.ModelAdmin):
    list_display = ['request_number', 'customer', 'project_name', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['request_number', 'customer__name', 'project_name']
    readonly_fields = ['created_at', 'updated_at']


class ProductionBatchInline(admin.TabularInline):
    model = ProductionBatch
    extra = 0
    fields = ['batch_number', 'truck', 'quantity_m3', 'status', 'departure_time', 'arrival_time']
    readonly_fields = ['batch_number', 'departure_time', 'arrival_time']


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number',
        'customer_name',
        'mix_design',
        'quantity_m3',
        'priority',
        'status',
        'scheduled_date',
    ]
    list_filter = ['status', 'priority']
    search_fields = ['order_number', 'customer_request__customer__name']
    readonly_fields = ['order_number', 'total_price', 'created_at', 'updated_at']
    inlines = [ProductionBatchInline]

    def customer_name(self, obj):
        return obj.customer_request.customer.name

    customer_name.short_description = 'العميل'


@admin.register(ProductionBatch)
class ProductionBatchAdmin(admin.ModelAdmin):
    list_display = [
        'batch_number',
        'order_number',
        'truck',
        'quantity_m3',
        'actual_quantity_m3',
        'status',
        'departure_time',
    ]
    list_filter = ['status']
    search_fields = ['batch_number', 'production_order__order_number']
    readonly_fields = ['batch_number', 'mixing_time', 'departure_time', 'arrival_time', 'pouring_start', 'pouring_end']

    def order_number(self, obj):
        return obj.production_order.order_number

    order_number.short_description = 'أمر الإنتاج'


@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = ['plate_number', 'driver_name', 'driver_phone', 'capacity_m3', 'status', 'is_active']
    list_filter = ['status', 'capacity_m3', 'is_active']
    search_fields = ['plate_number', 'driver_name']


@admin.register(DeliverySchedule)
class DeliveryScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'production_order',
        'delivery_date',
        'time_slot_from',
        'time_slot_to',
        'truck',
        'status',
        'sequence',
    ]
    list_filter = ['status', 'delivery_date']
    search_fields = ['production_order__order_number']


@admin.register(ProductionCost)
class ProductionCostAdmin(admin.ModelAdmin):
    list_display = ['production_order', 'cost_type', 'amount', 'date']
    list_filter = ['cost_type']
    search_fields = ['production_order__order_number']


class SiloTransactionInline(admin.TabularInline):
    model = SiloTransaction
    extra = 0
    fields = ['transaction_type', 'quantity_tons', 'previous_stock', 'new_stock', 'reference_number', 'date']
    readonly_fields = ['previous_stock', 'new_stock', 'date']
    ordering = ['-date']


@admin.register(Silo)
class SiloAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'name',
        'capacity_tons',
        'current_stock_tons',
        'minimum_order_tons',
        'critical_level_tons',
        'is_active',
    ]
    list_filter = ['is_active', 'cement_type']
    search_fields = ['code', 'name']
    inlines = [SiloTransactionInline]


@admin.register(SiloTransaction)
class SiloTransactionAdmin(admin.ModelAdmin):
    list_display = ['silo', 'transaction_type', 'quantity_tons', 'previous_stock', 'new_stock', 'date', 'created_by']
    list_filter = ['transaction_type', 'silo']
    search_fields = ['silo__code', 'reference_number']
    readonly_fields = ['previous_stock', 'new_stock']
