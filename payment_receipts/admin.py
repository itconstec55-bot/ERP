from django.contrib import admin

from .models import PaymentReceipt


@admin.register(PaymentReceipt)
class PaymentReceiptModelAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'receipt_type', 'date', 'amount', 'payment_method', 'is_posted')
    list_filter = ('receipt_type', 'payment_method', 'is_posted')
    search_fields = ('receipt_number', 'description')
