from django.contrib import admin

from .models import Cheque


@admin.register(Cheque)
class ChequeModelAdmin(admin.ModelAdmin):
    list_display = ('cheque_number', 'cheque_type', 'bank_name', 'amount', 'due_date', 'status')
    list_filter = ('cheque_type', 'status', 'bank_name')
    search_fields = ('cheque_number', 'payee_name')
