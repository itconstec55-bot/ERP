import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models, transaction

from accounts.models import JournalEntry


class PurchaseReturn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_number = models.CharField(max_length=50, unique=True, verbose_name='رقم المرتجع')
    date = models.DateField(verbose_name='التاريخ')
    supplier = models.ForeignKey('purchases.Supplier', on_delete=models.SET_NULL, null=True, verbose_name='المورد')
    original_invoice = models.ForeignKey(
        'purchases.PurchaseInvoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='فاتورة الشراء الأصلية',
    )
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المجموع الفرعي')
    vat_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='ضريبة القيمة المضافة')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الإجمالي')
    reason = models.TextField(blank=True, null=True, verbose_name='سبب المرتجع')
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القيد المحاسبي'
    )
    is_posted = models.BooleanField(default=False, verbose_name='مرحل')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مرتجع مشتريات'
        verbose_name_plural = 'مرتجعات المشتريات'
        ordering = ['-date']

    def __str__(self):
        return f'{self.return_number} - {self.supplier.name}'

    def calculate_totals(self):
        self.subtotal = sum(line.total for line in self.lines.all())
        self.vat_amount = self.subtotal * Decimal('0.14')
        self.total_amount = self.subtotal + self.vat_amount
        self.save(update_fields=['subtotal', 'vat_amount', 'total_amount'])

    def create_journal_entry(self):
        if self.is_posted:
            return self.journal_entry
        from common.accounting_service import JournalEntryService

        supplier_account = self.supplier.account or JournalEntryService.get_account('3100')
        purchases_account = JournalEntryService.get_account('1300')
        lines = [
            {
                'account': supplier_account,
                'debit': self.total_amount,
                'credit': 0,
                'description': f'مرتجع مشتريات - {self.supplier.name}',
            },
            {
                'account': purchases_account,
                'debit': 0,
                'credit': self.subtotal,
                'description': f'مشتريات مرتجعة - {self.return_number}',
            },
        ]
        if self.vat_amount > 0:
            lines.append(
                {
                    'account': JournalEntryService.get_account('1350'),
                    'debit': 0,
                    'credit': self.vat_amount,
                    'description': f'ضريبة مرتجع مشتريات - {self.return_number}',
                }
            )
        with transaction.atomic():
            entry = JournalEntryService.create_entry(
                entry_type='general',
                date=self.date,
                description=f'مرتجع مشتريات - {self.supplier.name} - {self.return_number}',
                entry_number=f'RET-P-{self.return_number}',
                lines=lines,
                created_by=self.created_by,
            )
            self.journal_entry = entry
            self.is_posted = True
            self.save(update_fields=['journal_entry', 'is_posted'])
        return entry


class PurchaseReturnLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey('purchases.Product', on_delete=models.PROTECT, verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name='الكمية')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='سعر الوحدة')
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الإجمالي')

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'
