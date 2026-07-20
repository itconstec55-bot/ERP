from django.contrib import admin

from .models import Asset, AssetCategory, DepreciationEntry


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'depreciation_rate')
    search_fields = ('name',)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'category',
        'purchase_price',
        'accumulated_depreciation',
        'net_book_value',
        'status',
    )
    list_filter = ('category', 'status', 'depreciation_method')
    search_fields = ('code', 'name')


@admin.register(DepreciationEntry)
class DepreciationEntryAdmin(admin.ModelAdmin):
    list_display = ('asset', 'date', 'amount', 'months', 'accumulated_after')
    list_filter = ('date',)
    search_fields = ('asset__name',)
