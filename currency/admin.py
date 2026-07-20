from django.contrib import admin
from .models import Currency, ExchangeRateHistory


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'exchange_rate_to_egp', 'is_base', 'is_active']


@admin.register(ExchangeRateHistory)
class ExchangeRateHistoryAdmin(admin.ModelAdmin):
    list_display = ['currency', 'rate', 'date']
