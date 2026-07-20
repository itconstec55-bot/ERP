import uuid

from django.db import models

from accounts.models import JournalEntry


class CreditNote(models.Model):
    TYPE_CHOICES = [('credit_note', 'إشعار دائن (مرتجع مبيعات)'), ('debit_note', 'إشعار مدين (مرتجع مشتريات)')]
    STATUS_CHOICES = [('draft', 'مسودة'), ('posted', 'مرحل'), ('cancelled', 'ملغي')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='النوع')
    note_number = models.CharField(max_length=50, unique=True, verbose_name='رقم الإشعار')
    date = models.DateField(verbose_name='التاريخ')
    customer = models.ForeignKey(
        'sales.Customer', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='العميل'
    )
    supplier = models.ForeignKey(
        'purchases.Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المورد'
    )
    original_invoice_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الفاتورة الأصلية')
    original_sales_invoice = models.ForeignKey(
        'sales.SalesInvoice', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='فاتورة المبيعات الأصلية'
    )
    original_purchase_invoice = models.ForeignKey(
        'purchases.PurchaseInvoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='فاتورة المشتريات الأصلية',
    )
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المبلغ')
    vat_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الضريبة')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الإجمالي')
    reason = models.TextField(blank=True, verbose_name='سبب الإشعار')
    is_posted = models.BooleanField(default=False, verbose_name='مرحل')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القيد المحاسبي'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'إشعار مدين/دائن'
        verbose_name_plural = 'إشعارات المدين والدائن'
        ordering = ['-date']

    def __str__(self):
        return f'{self.get_note_type_display()} - {self.note_number}'
