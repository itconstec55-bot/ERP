from django.apps import AppConfig


class TaxInvoicesConfig(AppConfig):
    default_auto_field = 'django.db.models.UUIDField'
    name = 'tax_invoices'
    verbose_name = 'الفواتير الضريبية'
