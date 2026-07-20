from django.contrib import admin

from .models import Budget, CostCenter


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'manager', 'is_active']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'account', 'year', 'budgeted_amount', 'actual_amount', 'status']
    list_filter = ['year', 'status', 'period']
