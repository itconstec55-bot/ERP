from django.contrib import admin

from .models import RFQ, Quotation, QuotationLine, RFQLine


@admin.register(RFQ)
class RFQAdmin(admin.ModelAdmin):
    list_display = ['number', 'requested_by', 'cost_center', 'date', 'status', 'created_by']
    list_filter = ['status', 'date']
    search_fields = ['number', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'created_by']


@admin.register(RFQLine)
class RFQLineAdmin(admin.ModelAdmin):
    list_display = ['rfq', 'product', 'quantity', 'estimated_unit_price']
    search_fields = ['rfq__number', 'product__name']


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ['rfq', 'supplier', 'received_date', 'status']
    list_filter = ['status', 'received_date']
    search_fields = ['rfq__number', 'supplier__name']


@admin.register(QuotationLine)
class QuotationLineAdmin(admin.ModelAdmin):
    list_display = ['quotation', 'product', 'quantity', 'unit_price', 'discount', 'delivery_days']
    search_fields = ['quotation__rfq__number', 'product__name']
