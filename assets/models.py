from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from accounts.models import Account, JournalEntry
from django.utils import timezone
import uuid
from datetime import timedelta
import math


class AssetCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم التصنيف')
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10,
                                             verbose_name='نسبة الإهلاك السنوية %')
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name='حساب الأصل')
    depreciation_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                              verbose_name='حساب مجمع الإهلاك', related_name='depr_categories')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تصنيف أصول'
        verbose_name_plural = 'تصنيفات الأصول'
        ordering = ['name']

    def __str__(self):
        return self.name


class Asset(models.Model):
    DEPRECIATION_METHOD_CHOICES = [
        ('straight_line', 'القسط الثابت'),
        ('declining', 'القسط المتناقص'),
    ]
    STATUS_CHOICES = [
        ('active', 'نشط'),
        ('depreciated', 'مستهلك بالكامل'),
        ('disposed', 'تم التخلص منه'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود الأصل')
    name = models.CharField(max_length=200, verbose_name='اسم الأصل')
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, verbose_name='التصنيف')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    purchase_date = models.DateField(verbose_name='تاريخ الشراء')
    purchase_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='سعر الشراء')
    salvage_value = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                         verbose_name='القيمة التخليصية')
    useful_life_years = models.IntegerField(default=5, verbose_name='العمر الإنتاجي بالسنوات')
    depreciation_method = models.CharField(max_length=20, choices=DEPRECIATION_METHOD_CHOICES,
                                            default='straight_line', verbose_name='طريقة الإهلاك')
    accumulated_depreciation = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                                    verbose_name='مجمع الإهلاك')
    net_book_value = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                          verbose_name='القيمة الدفترية الصافية')
    location = models.CharField(max_length=200, blank=True, null=True, verbose_name='الموقع')
    asset_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                       verbose_name='حساب الأصل', related_name='assets')
    depr_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name='حساب مجمع الإهلاك', related_name='accum_depr')
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                       verbose_name='قيد الشراء')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='الحالة')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'أصل ثابت'
        verbose_name_plural = 'الأصول الثابتة'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def save(self, *args, **kwargs):
        if self.accumulated_depreciation > self.purchase_price:
            self.accumulated_depreciation = self.purchase_price
        self.net_book_value = self.purchase_price - self.accumulated_depreciation
        if self.net_book_value <= 0:
            self.net_book_value = Decimal('0')
            if self.status == 'active':
                self.status = 'depreciated'
        super().save(*args, **kwargs)

    @property
    def annual_depreciation(self):
        if self.useful_life_years > 0:
            if self.depreciation_method == 'declining':
                rate = Decimal('2') / Decimal(str(self.useful_life_years))
                return self.net_book_value * rate
            return (self.purchase_price - self.salvage_value) / self.useful_life_years
        return Decimal('0')

    @property
    def monthly_depreciation(self):
        return self.annual_depreciation / Decimal('12')

    @property
    def depreciation_percentage(self):
        if self.purchase_price > 0:
            return (self.accumulated_depreciation / self.purchase_price) * 100
        return Decimal('0')

    def calculate_depreciation_for_period(self, months=1):
        depr = self.monthly_depreciation * months
        remaining = self.purchase_price - self.salvage_value - self.accumulated_depreciation
        if remaining <= 0:
            return Decimal('0')
        return min(depr, remaining)


class DepreciationEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, verbose_name='الأصل')
    date = models.DateField(verbose_name='التاريخ')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='مبلغ الإهلاك')
    accumulated_after = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                             verbose_name='المجمع بعد الإهلاك')
    months = models.IntegerField(default=1, verbose_name='عدد الأشهر')
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                       verbose_name='القيد المحاسبي')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'قيد إهلاك'
        verbose_name_plural = 'قيود الإهلاك'
        ordering = ['-date']

    def __str__(self):
        return f'{self.asset.name} - {self.amount}'

    def post_depreciation(self):
        from common.accounting_service import JournalEntryService
        depr_expense_account = self.asset.category.depreciation_account or JournalEntryService.get_account('5200')
        accum_depr_account = self.asset.depr_account or JournalEntryService.get_account('1400')
        lines = [
            {'account': depr_expense_account, 'debit': self.amount, 'credit': 0,
             'description': f'مصروف إهلاك - {self.asset.name}'},
            {'account': accum_depr_account, 'debit': 0, 'credit': self.amount,
             'description': f'مجمع إهلاك - {self.asset.name}'},
        ]
        with transaction.atomic():
            asset = Asset.objects.select_for_update().get(pk=self.asset.pk)
            entry = JournalEntryService.create_entry(
                entry_type='depreciation',
                date=self.date,
                description=f'إهلاك {asset.name} - {self.months} شهر',
                reference=f'DEP-{asset.code}',
                lines=lines,
                created_by=self.created_by,
            )
            asset.accumulated_depreciation += self.amount
            new_nbv = asset.purchase_price - asset.accumulated_depreciation
            update_fields = ['accumulated_depreciation', 'net_book_value']
            if new_nbv <= 0:
                asset.net_book_value = Decimal('0')
                asset.status = 'depreciated'
                update_fields.append('status')
            else:
                asset.net_book_value = new_nbv
            asset.save(update_fields=update_fields)
            self.asset = asset
            self.accumulated_after = asset.accumulated_depreciation
            self.journal_entry = entry
            self.save(update_fields=['accumulated_after', 'journal_entry'])
