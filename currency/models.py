import uuid
from django.db import models
from django.core.exceptions import ValidationError


class Currency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, unique=True, verbose_name='الكود')
    name = models.CharField(max_length=100, verbose_name='الاسم')
    symbol = models.CharField(max_length=10, verbose_name='الرمز')
    exchange_rate_to_egp = models.DecimalField(max_digits=15, decimal_places=6, default=1, verbose_name='سعر الصرف إلى ج.م')
    is_base = models.BooleanField(default=False, verbose_name='العملة الأساسية')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'عملة'
        verbose_name_plural = 'العملات'

    def __str__(self):
        return f'{self.code} - {self.name}'

    def clean(self):
        super().clean()
        if self.is_base:
            existing = Currency.objects.filter(is_base=True)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(f'العملة الأساسية الحالية هي "{existing.first().name}". لا يمكن تعيين عملة أساسية أخرى.')

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_base:
            Currency.objects.filter(is_base=True).exclude(pk=self.pk).update(is_base=False)
        super().save(*args, **kwargs)

    def convert_to_egp(self, amount):
        return amount * self.exchange_rate_to_egp

    def convert_from_egp(self, amount):
        if self.exchange_rate_to_egp:
            return amount / self.exchange_rate_to_egp
        return 0


class ExchangeRateHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='rate_history', verbose_name='العملة')
    rate = models.DecimalField(max_digits=15, decimal_places=6, verbose_name='سعر الصرف')
    date = models.DateField(verbose_name='التاريخ')
    notes = models.CharField(max_length=200, blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سجل سعر الصرف'
        verbose_name_plural = 'سجلات أسعار الصرف'
        ordering = ['-date']

    def __str__(self):
        return f'{self.currency.code} - {self.rate} - {self.date}'
