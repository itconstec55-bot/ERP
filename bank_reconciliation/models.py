import uuid
from django.db import models


class BankStatementItem(models.Model):
    TYPE_CHOICES = [
        ('credit', 'إيداع'),
        ('debit', 'سحب'),
    ]
    STATUS_CHOICES = [
        ('unmatched', 'غير مطابق'),
        ('matched', 'مطابق'),
        ('partial', 'مطابقة جزئية'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank_account = models.ForeignKey('treasury.Bank', on_delete=models.CASCADE, verbose_name='الحساب البنكي')
    transaction_date = models.DateField(verbose_name='التاريخ')
    description = models.CharField(max_length=500, verbose_name='الوصف')
    reference = models.CharField(max_length=100, blank=True, verbose_name='المرجع')
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المدين')
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الدائن')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unmatched', verbose_name='الحالة')
    matched_transaction = models.ForeignKey('treasury.BankTransaction', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المعاملة المطابقة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'بند كشف حساب بنكي'
        verbose_name_plural = 'بنود كشف الحساب البنكي'
        ordering = ['-transaction_date']

    def __str__(self):
        return f'{self.description} - {self.transaction_date}'

    @property
    def amount(self):
        if self.credit_amount:
            return self.credit_amount
        return -self.debit_amount


class ReconciliationSession(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank_account = models.ForeignKey('treasury.Bank', on_delete=models.CASCADE, verbose_name='الحساب البنكي')
    period_start = models.DateField(verbose_name='من تاريخ')
    period_end = models.DateField(verbose_name='إلى تاريخ')
    book_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='رصيد الدفتر')
    bank_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='رصيد البنك')
    reconciled_diff = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='فرق التسوية')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress', verbose_name='الحالة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'جلسة تسوية بنكية'
        verbose_name_plural = 'جلسات التسوية البنكية'

    def __str__(self):
        return f'{self.bank_account} - {self.period_start} إلى {self.period_end}'

    def calculate_difference(self):
        self.reconciled_diff = self.bank_balance - self.book_balance
        self.save(update_fields=['reconciled_diff'])
        return self.reconciled_diff
