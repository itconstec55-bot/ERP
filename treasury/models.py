import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models, transaction

from accounts.models import Account, JournalEntry
from common.accounting_service import JournalEntryService
from common.exceptions import AccountingError
from common.models import SequenceNumber
from common.validators import validate_positive_decimal


class Bank(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم البنك')
    branch = models.CharField(max_length=200, blank=True, null=True, verbose_name='الفرع')
    account_number = models.CharField(max_length=50, verbose_name='رقم الحساب')
    iban = models.CharField(max_length=50, blank=True, null=True, verbose_name='رقم الآيبان')
    swift_code = models.CharField(max_length=20, blank=True, null=True, verbose_name='الكود السويفت')
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الحساب المحاسبي'
    )
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الرصيد الحالي')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='نشط')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'بنك'
        verbose_name_plural = 'البنوك'
        ordering = ['name']
        permissions = [
            ('approve_banktransaction', 'اعتماد معاملة بنكية'),
            ('print_banktransaction', 'طباعة معاملة بنكية'),
            ('export_banktransaction', 'تصدير المعاملات البنكية'),
        ]

    def __str__(self):
        return f'{self.name} - {self.account_number}'


class Safe(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم الخزينة')
    responsible_person = models.CharField(max_length=200, blank=True, null=True, verbose_name='المسئول')
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الحساب المحاسبي'
    )
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الرصيد الحالي')
    maximum_limit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الحد الأقصى')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='نشط')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'خزينة'
        verbose_name_plural = 'الخزائن'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} - الرصيد: {self.current_balance}'


class BankTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'إيداع'),
        ('withdrawal', 'سحب'),
        ('transfer_in', 'تحويل وارد'),
        ('transfer_out', 'تحويل صادر'),
        ('check_in', 'إيداع شيك'),
        ('check_out', 'صرف شيك'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT, verbose_name='البنك')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name='نوع المعاملة')
    date = models.DateField(verbose_name='التاريخ', default=date.today)
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='المبلغ', validators=[validate_positive_decimal]
    )
    balance_after = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الرصيد بعد المعاملة')
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name='رقم المرجع')
    check_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='رقم الشيك')
    description = models.TextField(verbose_name='البيان')
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القيد المحاسبي'
    )
    counterparty_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_tx_counterparty',
        verbose_name='حساب الطرف المقابل',
    )
    is_posted = models.BooleanField(default=False, verbose_name='مرحل للاستاذ العام')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'معاملة بنكية'
        verbose_name_plural = 'المعاملات البنكية'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date'], name='bt_date_idx'),
            models.Index(fields=['bank', '-date'], name='bt_bank_date_idx'),
        ]

    def __str__(self):
        return f'{self.bank.name} - {self.get_transaction_type_display()} - {self.amount}'

    def _post_to_gl(self):
        bank_gl = self.bank.account
        if bank_gl is None:
            raise AccountingError(
                f'لا يوجد حساب محاسبي مرتبط بالبنك "{self.bank.name}". يرجى ربط حساب محاسبي بالبنك أولاً.'
            )
        counterparty = self.counterparty_account
        if counterparty is None:
            raise AccountingError('يجب تحديد حساب الطرف المقابل للمعاملة البنكية.')
        incoming = self.transaction_type in ['deposit', 'transfer_in', 'check_in']
        desc = (self.description or '')[:100]
        if incoming:
            lines = [
                {
                    'account': bank_gl,
                    'debit': self.amount,
                    'credit': Decimal('0'),
                    'description': f'إيداع نقدي - {self.bank.name}',
                },
                {
                    'account': counterparty,
                    'debit': Decimal('0'),
                    'credit': self.amount,
                    'description': f'طرف مقابل - {desc}',
                },
            ]
            entry_type = 'receipt'
        else:
            lines = [
                {
                    'account': counterparty,
                    'debit': self.amount,
                    'credit': Decimal('0'),
                    'description': f'طرف مقابل - {desc}',
                },
                {
                    'account': bank_gl,
                    'debit': Decimal('0'),
                    'credit': self.amount,
                    'description': f'سحب نقدي - {self.bank.name}',
                },
            ]
            entry_type = 'payment'
        return JournalEntryService.create_entry(
            entry_type=entry_type,
            date=self.date,
            description=f'{self.get_transaction_type_display()} - {self.description}',
            reference=self.reference_number or '',
            lines=lines,
            created_by=self.created_by,
            entry_number=SequenceNumber.get_next_number('journal_entry'),
        )

    def save(self, *args, **kwargs):
        is_new = not self.pk
        if is_new and self.journal_entry_id is None and not self.is_posted:
            with transaction.atomic():
                locked_bank = Bank.objects.select_for_update().get(pk=self.bank.pk)
                if self.transaction_type in ['deposit', 'transfer_in', 'check_in']:
                    locked_bank.current_balance += self.amount
                elif self.transaction_type in ['withdrawal', 'transfer_out', 'check_out']:
                    if locked_bank.current_balance < self.amount:
                        raise AccountingError(
                            f'رصيد البنك "{locked_bank.name}" غير كافٍ. '
                            f'الرصيد الحالي: {locked_bank.current_balance}, المطلوب: {self.amount}'
                        )
                    locked_bank.current_balance -= self.amount
                locked_bank.save(update_fields=['current_balance'])
                self.bank = locked_bank
                self.balance_after = locked_bank.current_balance
                self.journal_entry = self._post_to_gl()
                self.is_posted = True
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class SafeTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [('deposit', 'إيداع'), ('withdrawal', 'سحب'), ('transfer', 'تحويل')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    safe = models.ForeignKey(Safe, on_delete=models.PROTECT, verbose_name='الخزينة')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name='نوع المعاملة')
    date = models.DateField(verbose_name='التاريخ', default=date.today)
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='المبلغ', validators=[validate_positive_decimal]
    )
    balance_after = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الرصيد بعد المعاملة')
    description = models.TextField(verbose_name='البيان')
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القيد المحاسبي'
    )
    counterparty_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='safe_tx_counterparty',
        verbose_name='حساب الطرف المقابل',
    )
    is_posted = models.BooleanField(default=False, verbose_name='مرحل للاستاذ العام')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'معاملة خزينة'
        verbose_name_plural = 'معاملات الخزائن'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date'], name='st_date_idx'),
            models.Index(fields=['safe', '-date'], name='st_safe_date_idx'),
        ]

    def __str__(self):
        return f'{self.safe.name} - {self.get_transaction_type_display()} - {self.amount}'

    def _post_to_gl(self):
        safe_gl = self.safe.account
        if safe_gl is None:
            raise AccountingError(
                f'لا يوجد حساب محاسبي مرتبط بالخزينة "{self.safe.name}". يرجى ربط حساب محاسبي بالخزينة أولاً.'
            )
        counterparty = self.counterparty_account
        if counterparty is None:
            raise AccountingError('يجب تحديد حساب الطرف المقابل للمعاملة الخزينة.')
        incoming = self.transaction_type in ['deposit', 'transfer']
        desc = (self.description or '')[:100]
        if incoming:
            lines = [
                {
                    'account': safe_gl,
                    'debit': self.amount,
                    'credit': Decimal('0'),
                    'description': f'إيداع نقدي - {self.safe.name}',
                },
                {
                    'account': counterparty,
                    'debit': Decimal('0'),
                    'credit': self.amount,
                    'description': f'طرف مقابل - {desc}',
                },
            ]
            entry_type = 'receipt'
        else:
            lines = [
                {
                    'account': counterparty,
                    'debit': self.amount,
                    'credit': Decimal('0'),
                    'description': f'طرف مقابل - {desc}',
                },
                {
                    'account': safe_gl,
                    'debit': Decimal('0'),
                    'credit': self.amount,
                    'description': f'سحب نقدي - {self.safe.name}',
                },
            ]
            entry_type = 'payment'
        return JournalEntryService.create_entry(
            entry_type=entry_type,
            date=self.date,
            description=f'{self.get_transaction_type_display()} - {self.description}',
            reference='',
            lines=lines,
            created_by=self.created_by,
            entry_number=SequenceNumber.get_next_number('journal_entry'),
        )

    def save(self, *args, **kwargs):
        is_new = not self.pk
        if is_new and self.journal_entry_id is None and not self.is_posted:
            with transaction.atomic():
                locked_safe = Safe.objects.select_for_update().get(pk=self.safe.pk)
                if self.transaction_type in ['deposit', 'transfer']:
                    if locked_safe.maximum_limit > 0:
                        new_balance = locked_safe.current_balance + self.amount
                        if new_balance > locked_safe.maximum_limit:
                            raise AccountingError(
                                f'الإيداع سيتجاوز الحد الأقصى للخزينة "{locked_safe.name}". '
                                f'الحد الأقصى: {locked_safe.maximum_limit}, الرصيد بعد الإيداع: {new_balance}'
                            )
                    locked_safe.current_balance += self.amount
                elif self.transaction_type == 'withdrawal':
                    if locked_safe.current_balance < self.amount:
                        raise AccountingError(
                            f'رصيد الخزينة "{locked_safe.name}" غير كافٍ. '
                            f'الرصيد الحالي: {locked_safe.current_balance}, المطلوب: {self.amount}'
                        )
                    locked_safe.current_balance -= self.amount
                locked_safe.save(update_fields=['current_balance'])
                self.safe = locked_safe
                self.balance_after = locked_safe.current_balance
                self.journal_entry = self._post_to_gl()
                self.is_posted = True
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)
