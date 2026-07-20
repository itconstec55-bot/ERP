from django.contrib import admin
from .models import Company, CompanyBranch


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'tax_number', 'phone', 'city']
    search_fields = ['name', 'tax_number']


@admin.register(CompanyBranch)
class CompanyBranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'city', 'is_active', 'is_default']
    list_filter = ['is_active', 'is_default']
