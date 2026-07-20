from django.contrib import admin
from .models import GoodsReceivedNote, GoodsReceivedLine


@admin.register(GoodsReceivedNote)
class GoodsReceivedNoteAdmin(admin.ModelAdmin):
    list_display = ['grn_number', 'supplier', 'purchase_order', 'date', 'status', 'created_by']
    list_filter = ['status', 'date']
    search_fields = ['grn_number', 'supplier__name']
    readonly_fields = ['created_at', 'updated_at', 'created_by']


@admin.register(GoodsReceivedLine)
class GoodsReceivedLineAdmin(admin.ModelAdmin):
    list_display = ['grn', 'product', 'quantity_received', 'unit_price']
    search_fields = ['grn__grn_number', 'product__name']
