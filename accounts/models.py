import logging
from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid

from common.validators import validate_balanced_entry

logger = logging.getLogger('accounting')


class AccountType(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('asset', 'أصول'),
        ('liability', 'خصوم'),
        ('equity', 'حقوق الملكية'),
        ('revenue', 'إيرادات'),
        ('expense', 'مصروفات'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='اسم النوع')
    code = models.CharField(max_length=20, unique=True, verbose_name='كود النوع')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, verbose_name='نوع الحساب')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'نوع حساب'
        verbose_name_plural = 'أنواع الحسابات'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود الحساب')
    name = models.CharField(max_length=200, verbose_name='اسم الحساب')
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT, verbose_name='نوع الحساب', related_name='accounts')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='children', verbose_name='الحساب الأب')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    opening_balance = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                          verbose_name='الرصيد الافتتاحي')
    current_balance = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                          verbose_name='الرصيد الحالي')
    is_bank = models.BooleanField(default=False, verbose_name='حساب بنكي')
    is_safe = models.BooleanField(default=False, verbose_name='حساب خزينة')
    tax_account = models.BooleanField(default=False, verbose_name='حساب ضريبي')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'حساب'
        verbose_name_plural = 'الحسابات'
        ordering = ['code']
        indexes = [
            models.Index(fields=['account_type', 'is_active'], name='acc_type_active_idx'),
            models.Index(fields=['parent', 'is_active'], name='acc_parent_active_idx'),
        ]

    def __str__(self):
        return f'{self.code} - {self.name}'

    def get_balance_display(self):
        if self.account_type.account_type in ['asset', 'expense']:
            if self.current_balance >= 0:
                return f'مدين: {self.current_balance}'
            return f'دائن: {abs(self.current_balance)}'
        else:
            if self.current_balance >= 0:
                return f'دائن: {self.current_balance}'
            return f'مدين: {abs(self.current_balance)}'

    def clean(self):
        super().clean()
        if self.parent:
            if self.parent_id == self.pk:
                raise ValidationError('لا يمكن أن يكون الحساب أبناً لنفسه')
            node = self.parent.parent
            visited = {self.parent_id}
            while node is not None:
                if node.pk == self.pk:
                    raise ValidationError('يوجد دورة في هيكل الحسابات')
                visited.add(node.pk)
                node = node.parent
        if self.is_bank and self.is_safe:
            raise ValidationError('لا يمكن أن يكون الحساب بنكياً وخزينة في نفس الوقت')

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.current_balance = self.opening_balance
        else:
            # استخدام select_for_update() لمنع حالة التسابق (Race Condition)
            # عند تعديل الرصيد الافتتاحي من طلبين متزامنين
            try:
                old = Account.objects.select_for_update().get(pk=self.pk)
                if old.opening_balance != self.opening_balance:
                    diff = self.opening_balance - old.opening_balance
                    self.current_balance = old.current_balance + diff
            except Account.DoesNotExist:
                pass
        super().save(*args, **kwargs)


class JournalEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('general', 'قيد عام'),
        ('purchase', 'قيد مشتريات'),
        ('sale', 'قيد مبيعات'),
        ('receipt', 'قيد تحصيل'),
        ('payment', 'قيد دفع'),
        ('depreciation', 'قيد إهلاك'),
        ('payroll', 'قيد رواتب'),
        ('adjustment', 'قيد تسوية'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry_number = models.CharField(max_length=50, unique=True, verbose_name='رقم القيد')
    file_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='رقم الملف', db_index=True)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, verbose_name='نوع القيد')
    date = models.DateField(default=timezone.now, verbose_name='التاريخ')
    description = models.TextField(verbose_name='البيان')
    reference = models.CharField(max_length=100, blank=True, null=True, verbose_name='المرجع')
    is_posted = models.BooleanField(default=False, verbose_name='مرحل')
    is_reversed = models.BooleanField(default=False, verbose_name='معكوس')
    total_debit = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='إجمالي المدين')
    total_credit = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='إجمالي الدائن')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قيد محاسبي'
        verbose_name_plural = 'القيود المحاسبية'
        ordering = ['-date', '-entry_number']
        indexes = [
            models.Index(fields=['entry_type', '-date'], name='je_type_date_idx'),
            models.Index(fields=['is_posted', '-date'], name='je_posted_date_idx'),
            models.Index(fields=['reference'], name='je_reference_idx'),
            models.Index(fields=['created_by', '-date'], name='je_user_date_idx'),
        ]

    def __str__(self):
        return f'{self.entry_number} - {self.description}'

    def calculate_totals(self):
        lines = self.lines.all()
        self.total_debit = sum(line.debit for line in lines)
        self.total_credit = sum(line.credit for line in lines)
        self.save(update_fields=['total_debit', 'total_credit'])

    def is_balanced(self):
        return self.total_debit == self.total_credit

    def post(self):
        with transaction.atomic():
            entry = JournalEntry.objects.select_for_update().get(pk=self.pk)
            if not entry.is_balanced():
                raise ValueError('القيد غير متوازن - المدين يجب أن يساوي الدائن')
            if entry.is_posted:
                raise ValueError('القيد مرحل بالفعل')
            if entry.is_reversed:
                raise ValueError('القيد معكوس - لا يمكن ترحيل قيد معكوس')
            for line in entry.lines.all():
                if line.account.parent is not None:
                    raise ValueError(f'لا يمكن الترحيل على حساب أب/رئيسي: {line.account.code}')
            account_ids = list(entry.lines.values_list('account_id', flat=True).distinct())
            locked_accounts = Account.objects.filter(id__in=account_ids).select_for_update()
            locked_map = {a.id: a for a in locked_accounts}

            for line in entry.lines.all():
                account = locked_map[line.account_id]
                account.current_balance += line.debit - line.credit
                account.save(update_fields=['current_balance'])
            entry.is_posted = True
            entry.save(update_fields=['is_posted'])
            logger.info('Journal entry %s posted successfully', entry.entry_number)

    def reverse(self):
        with transaction.atomic():
            entry = JournalEntry.objects.select_for_update().get(pk=self.pk)
            if not entry.is_posted:
                raise ValueError('لا يمكن إرجاع قيد غير مرحل')
            if entry.is_reversed:
                raise ValueError('القيد معكوس بالفعل')
            account_ids = list(entry.lines.values_list('account_id', flat=True).distinct())
            locked_accounts = Account.objects.filter(id__in=account_ids).select_for_update()
            locked_map = {a.id: a for a in locked_accounts}

            for line in entry.lines.all():
                account = locked_map[line.account_id]
                account.current_balance += line.credit - line.debit
                account.save(update_fields=['current_balance'])
            entry.is_reversed = True
            entry.is_posted = False
            entry.save(update_fields=['is_reversed', 'is_posted'])
            logger.info('Journal entry %s reversed successfully', entry.entry_number)


class JournalEntryLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE,
                                       related_name='lines', verbose_name='القيد المحاسبي')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, verbose_name='الحساب')
    debit = models.DecimalField(max_digits=20, decimal_places=10, default=0, verbose_name='مدين')
    credit = models.DecimalField(max_digits=20, decimal_places=10, default=0, verbose_name='دائن')
    description = models.CharField(max_length=300, blank=True, null=True, verbose_name='البيان')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'بند القيد'
        verbose_name_plural = 'بنود القيود'
        ordering = ['journal_entry', 'id']
        indexes = [
            models.Index(fields=['account', 'journal_entry'], name='jel_acct_entry_idx'),
            models.Index(fields=['account'], name='jel_account_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(debit__gt=0, credit=0) |
                    models.Q(debit=0, credit__gt=0)
                ),
                name='jel_debit_or_credit_exclusive',
            ),
            models.CheckConstraint(
                check=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name='jel_non_negative_amounts',
            ),
        ]

    def __str__(self):
        return f'{self.account.name} - مدين: {self.debit} دائن: {self.credit}'

    def clean(self):
        super().clean()
        # Validate that either debit or credit is set, but not both
        if self.debit and self.credit:
            raise ValidationError('لا يمكن أن يكون السطر مديناً ودائناً في نفس الوقت')
        # Validate that at least one is set
        if not self.debit and not self.credit:
            raise ValidationError('يجب تحديد قيمة مدين أو دائن للسطر')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # تحديث إجماليات القيد الأب بشكل فعال (استعلام واحد بدلاً من اثنين)
        from django.db.models import Sum, Value
        from django.db.models.functions import Coalesce
        totals = self.journal_entry.lines.aggregate(
            total_debit=Coalesce(Sum('debit'), Decimal('0')),
            total_credit=Coalesce(Sum('credit'), Decimal('0')),
        )
        self.journal_entry.total_debit = totals['total_debit']
        self.journal_entry.total_credit = totals['total_credit']
        self.journal_entry.save(update_fields=['total_debit', 'total_credit'])
