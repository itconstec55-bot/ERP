from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from accounts.models import Account, JournalEntry
import uuid


class SalesReturn(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('posted', 'مرحل'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_number = models.CharField(max_length=50, unique=True, verbose_name='رقم المرتجع')
    date = models.DateField(verbose_name='التاريخ')
    customer = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, verbose_name='العميل')
    original_invoice = models.ForeignKey('sales.SalesInvoice', on_delete=models.SET_NULL,
                                         null=True, blank=True, verbose_name='فاتورة المبيعات الأصلية')
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المجموع الفرعي')
    vat_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='ضريبة القيمة المضافة')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الإجمالي')
    reason = models.TextField(blank=True, null=True, verbose_name='سبب المرتجع')
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name='القيد المحاسبي')
    is_posted = models.BooleanField(default=False, verbose_name='مرحل')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مرتجع مبيعات'
        verbose_name_plural = 'مرتجعات المبيعات'
        ordering = ['-date']

    def __str__(self):
        return f'{self.return_number} - {self.customer.name}'

    def calculate_totals(self):
        self.subtotal = sum(line.total for line in self.lines.all())
        self.vat_amount = self.subtotal * Decimal('0.14')
        self.total_amount = self.subtotal + self.vat_amount
        self.save(update_fields=['subtotal', 'vat_amount', 'total_amount'])

    def create_journal_entry(self):
        if self.is_posted:
            return self.journal_entry
        from common.accounting_service import JournalEntryService
        customer_account = self.customer.account or JournalEntryService.get_account('1100')
        revenue_account = JournalEntryService.get_account('6100')
        lines = [
            {'account': customer_account, 'debit': 0, 'credit': self.total_amount,
             'description': f'مرتجع مبيعات - {self.customer.name}'},
            {'account': revenue_account, 'debit': self.subtotal, 'credit': 0,
             'description': f'إيرادات مرتجعات - {self.return_number}'},
        ]
        if self.vat_amount > 0:
            vat_account = JournalEntryService.get_account('3200')
            lines.append({'account': vat_account, 'debit': self.vat_amount, 'credit': 0,
                          'description': f'ضريبة مرتجع - {self.return_number}'})

        with transaction.atomic():
            entry = JournalEntryService.create_entry(
                entry_type='general',
                date=self.date,
                description=f'مرتجع مبيعات - {self.customer.name} - {self.return_number}',
                entry_number=f'RET-S-{self.return_number}',
                lines=lines,
                created_by=self.created_by,
            )
            self.journal_entry = entry
            self.is_posted = True
            self.save(update_fields=['journal_entry', 'is_posted'])
        return entry


class SalesReturnLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name='lines', verbose_name='مرتجع المبيعات')
    product = models.ForeignKey('purchases.Product', on_delete=models.PROTECT, verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name='الكمية')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='سعر الوحدة')
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الإجمالي')

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'
