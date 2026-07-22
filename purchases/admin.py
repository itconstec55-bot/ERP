from django.contrib import admin

from .models import (
    CatalogSettings,
    Product,
    ProductCategory,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    Supplier,
    UnitOfMeasure,
)


class PurchaseInvoiceLineInline(admin.TabularInline):
    model = PurchaseInvoiceLine
    extra = 1
    fields = ('product', 'quantity', 'unit_price', 'discount_percent', 'total_price')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'supplier_type', 'phone', 'current_balance', 'is_active')
    list_filter = ('supplier_type', 'is_active')
    search_fields = ('code', 'name', 'tax_number')


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'base_unit', 'conversion_factor', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'symbol')


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'parent', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(CatalogSettings)
class CatalogSettingsAdmin(admin.ModelAdmin):
    list_display = (
        '__str__',
        'default_unit',
        'default_category',
        'enforce_unit',
        'enforce_category',
        'allow_decimal_quantity',
    )

    def has_add_permission(self, request):
        return not CatalogSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'category',
        'unit_of_measure',
        'purchase_price',
        'selling_price',
        'current_stock',
        'is_active',
    )
    list_filter = ('category', 'unit_of_measure', 'is_active')
    search_fields = ('code', 'name', 'barcode')


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'supplier', 'date', 'total_amount', 'paid_amount', 'is_tax_invoice', 'is_posted')
    list_filter = ('is_tax_invoice', 'is_posted', 'payment_method')
    search_fields = ('invoice_number', 'supplier__name')
    inlines = [PurchaseInvoiceLineInline]
    readonly_fields = ('subtotal', 'vat_amount', 'total_amount', 'remaining_amount')


@admin.register(PurchaseInvoiceLine)
class PurchaseInvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'product', 'quantity', 'unit_price', 'total_price')
    search_fields = ('product__name',)
