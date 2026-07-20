from django.contrib import admin

from .models import Customer, SalesInvoice, SalesInvoiceLine


class SalesInvoiceLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 1
    fields = (
        'product',
        'quantity',
        'unit_price',
        'cost_price',
        'discount_percent',
        'total_price',
        'profit',
        'profit_margin',
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'customer_type', 'phone', 'current_balance', 'is_active')
    list_filter = ('customer_type', 'is_active')
    search_fields = ('code', 'name', 'tax_number')


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'customer',
        'date',
        'total_amount',
        'paid_amount',
        'gross_profit',
        'is_tax_invoice',
        'is_posted',
    )
    list_filter = ('is_tax_invoice', 'is_posted', 'payment_method')
    search_fields = ('invoice_number', 'customer__name')
    inlines = [SalesInvoiceLineInline]
    readonly_fields = ('subtotal', 'vat_amount', 'total_amount', 'remaining_amount', 'cost_of_goods', 'gross_profit')


@admin.register(SalesInvoiceLine)
class SalesInvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'product', 'quantity', 'unit_price', 'total_price', 'profit', 'profit_margin')
    search_fields = ('product__name',)
