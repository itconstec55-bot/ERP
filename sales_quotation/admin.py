from django.contrib import admin

from .models import SalesQuotation, SalesQuotationLine


class SalesQuotationLineInline(admin.TabularInline):
    model = SalesQuotationLine
    extra = 0
    readonly_fields = ('total_price',)


@admin.register(SalesQuotation)
class SalesQuotationAdmin(admin.ModelAdmin):
    list_display = ('quotation_number', 'customer', 'date', 'valid_until', 'status', 'total_amount')
    list_filter = ('status', 'date')
    search_fields = ('quotation_number', 'customer__name')
    readonly_fields = ('subtotal', 'vat_amount', 'total_amount', 'created_at', 'updated_at')
    inlines = [SalesQuotationLineInline]
