from django.contrib import admin

from .models import StockMovement, Warehouse, WarehouseProduct


class WarehouseProductInline(admin.TabularInline):
    model = WarehouseProduct
    extra = 0


class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'location', 'manager', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')
    inlines = [WarehouseProductInline]


class WarehouseProductAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'product', 'quantity', 'minimum_quantity', 'is_low')
    list_filter = ('warehouse',)
    search_fields = ('product__name',)


class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'movement_number',
        'movement_type',
        'warehouse',
        'to_warehouse',
        'product',
        'quantity',
        'date',
        'performed_by',
    )
    list_filter = ('movement_type', 'warehouse')
    search_fields = ('movement_number', 'product__name')
    readonly_fields = ('total_cost',)


admin.site.register(Warehouse, WarehouseAdmin)
admin.site.register(WarehouseProduct, WarehouseProductAdmin)
admin.site.register(StockMovement, StockMovementAdmin)
