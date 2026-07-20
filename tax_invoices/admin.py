from django.contrib import admin
from .models import ETAConnection, TaxInvoice


@admin.register(ETAConnection)
class ETAConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'environment', 'is_active', 'created_at']
    list_filter = ['environment', 'is_active']


@admin.register(TaxInvoice)
class TaxInvoiceAdmin(admin.ModelAdmin):
    list_display = ['tax_invoice_number', 'sales_invoice', 'document_type', 'status',
                    'total_amount', 'submitted_at']
    list_filter = ['status', 'document_type', 'created_at']
    readonly_fields = ['eta_uuid', 'eta_submission_uuid', 'eta_long_id', 'eta_internal_id',
                       'eta_qr_code', 'eta_pdf_url', 'submitted_at', 'validated_at']
    search_fields = ['tax_invoice_number']
