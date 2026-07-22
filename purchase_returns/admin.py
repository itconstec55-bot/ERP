from django.contrib import admin

from .models import PurchaseReturn, PurchaseReturnLine


class PurchaseReturnLineInline(admin.TabularInline):
    model = PurchaseReturnLine
    extra = 1


@admin.register(PurchaseReturn)
class PurchaseReturnModelAdmin(admin.ModelAdmin):
    list_display = ('return_number', 'date', 'supplier', 'total_amount', 'is_posted')
    list_filter = ('is_posted', 'date')
    search_fields = ('return_number', 'supplier__name')
    inlines = [PurchaseReturnLineInline]
