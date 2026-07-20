from django.contrib import admin

from .models import CertificateItem, Contract, ContractItem, Contractor, ContractorPayment, InterimCertificate


class ContractItemInline(admin.TabularInline):
    model = ContractItem
    extra = 3
    fields = ['item_number', 'description', 'unit', 'quantity', 'unit_price', 'total_price', 'order']


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'contractor_type', 'speciality', 'current_balance', 'status', 'is_active']
    list_filter = ['status', 'contractor_type', 'is_active']
    search_fields = ['code', 'name', 'phone', 'tax_number']
    readonly_fields = ['current_balance', 'created_at', 'updated_at']


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ['contract_number', 'title', 'contractor', 'contract_amount', 'completion_percentage', 'status']
    list_filter = ['status', 'contract_type']
    search_fields = ['contract_number', 'title', 'contractor__name']
    readonly_fields = [
        'contract_number',
        'vat_amount',
        'total_with_vat',
        'total_certified',
        'total_paid',
        'total_retained',
        'created_at',
        'updated_at',
    ]
    inlines = [ContractItemInline]


class CertificateItemInline(admin.TabularInline):
    model = CertificateItem
    extra = 2
    fields = ['contract_item', 'previous_quantity', 'current_quantity', 'total_executed', 'amount']


@admin.register(InterimCertificate)
class InterimCertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_number', 'contract', 'period_number', 'gross_amount', 'net_amount', 'status']
    list_filter = ['status']
    search_fields = ['certificate_number', 'contract__contract_number']
    readonly_fields = [
        'certificate_number',
        'gross_amount',
        'retention_amount',
        'advance_deduction',
        'vat_amount',
        'net_amount',
        'is_posted',
        'created_at',
        'updated_at',
    ]
    inlines = [CertificateItemInline]


@admin.register(ContractorPayment)
class ContractorPaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_number', 'contract', 'amount', 'payment_method', 'payment_date', 'status']
    list_filter = ['status', 'payment_method']
    search_fields = ['payment_number', 'contract__contractor__name']
    readonly_fields = ['payment_number', 'is_posted', 'created_at', 'updated_at']
