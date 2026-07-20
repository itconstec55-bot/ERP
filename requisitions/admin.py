from django.contrib import admin

from .models import Requisition, RequisitionLine


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ['number', 'requested_by', 'cost_center', 'date', 'priority', 'status', 'created_by']
    list_filter = ['status', 'priority', 'date']
    search_fields = ['number', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'number']


@admin.register(RequisitionLine)
class RequisitionLineAdmin(admin.ModelAdmin):
    list_display = ['requisition', 'product', 'quantity', 'uom', 'estimated_unit_price']
    search_fields = ['requisition__number', 'product__name']
