from django.contrib import admin
from .models import BankStatementItem, ReconciliationSession


@admin.register(BankStatementItem)
class BankStatementItemAdmin(admin.ModelAdmin):
    list_display = ['transaction_date', 'bank_account', 'description', 'debit_amount', 'credit_amount', 'status']
    list_filter = ['status', 'bank_account']


@admin.register(ReconciliationSession)
class ReconciliationSessionAdmin(admin.ModelAdmin):
    list_display = ['bank_account', 'period_start', 'period_end', 'book_balance', 'bank_balance', 'status']
    list_filter = ['status']
