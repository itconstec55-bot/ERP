from django.contrib import admin

from .models import Bank, BankTransaction, Safe, SafeTransaction


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'account_number', 'current_balance', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'account_number')


@admin.register(Safe)
class SafeAdmin(admin.ModelAdmin):
    list_display = ('name', 'responsible_person', 'current_balance', 'maximum_limit', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ('bank', 'transaction_type', 'date', 'amount', 'balance_after')
    list_filter = ('transaction_type', 'bank')
    search_fields = ('description', 'reference_number')


@admin.register(SafeTransaction)
class SafeTransactionAdmin(admin.ModelAdmin):
    list_display = ('safe', 'transaction_type', 'date', 'amount', 'balance_after')
    list_filter = ('transaction_type', 'safe')
    search_fields = ('description',)
