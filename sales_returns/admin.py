from django.contrib import admin
from .models import SalesReturn, SalesReturnLine


class SalesReturnLineInline(admin.TabularInline):
    model = SalesReturnLine
    extra = 1


@admin.register(SalesReturn)
class SalesReturnModelAdmin(admin.ModelAdmin):
    list_display = ('return_number', 'date', 'customer', 'total_amount', 'is_posted')
    list_filter = ('is_posted', 'date')
    search_fields = ('return_number', 'customer__name')
    inlines = [SalesReturnLineInline]
