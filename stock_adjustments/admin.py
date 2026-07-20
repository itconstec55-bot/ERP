from django.contrib import admin

from .models import StockAdjustment, StockAdjustmentLine


class StockAdjustmentLineInline(admin.TabularInline):
    model = StockAdjustmentLine
    extra = 1


@admin.register(StockAdjustment)
class StockAdjustmentModelAdmin(admin.ModelAdmin):
    list_display = ('adjustment_number', 'date', 'adjustment_type', 'warehouse', 'status')
    list_filter = ('adjustment_type', 'status')
    inlines = [StockAdjustmentLineInline]
