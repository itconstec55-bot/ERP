from django.contrib import admin

from .models import SalesOrder, SalesOrderLine


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'date', 'status', 'created_by']
    list_filter = ['status', 'date']
    search_fields = ['order_number', 'customer__name']
    readonly_fields = ['created_at', 'updated_at', 'created_by']


@admin.register(SalesOrderLine)
class SalesOrderLineAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'unit_price', 'invoiced_quantity']
    search_fields = ['order__order_number', 'product__name']
