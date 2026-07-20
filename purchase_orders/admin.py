from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderLine


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'supplier', 'date', 'status', 'created_by']
    list_filter = ['status', 'date']
    search_fields = ['order_number', 'supplier__name']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    inlines = []


@admin.register(PurchaseOrderLine)
class PurchaseOrderLineAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'unit_price', 'received_quantity']
    search_fields = ['order__order_number', 'product__name']
