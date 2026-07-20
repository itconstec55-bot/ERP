import uuid

from django.db import models


class CostCenter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, verbose_name='الكود')
    name = models.CharField(max_length=200, verbose_name='الاسم')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='المركز الأب'
    )
    description = models.TextField(blank=True, verbose_name='الوصف')
    manager = models.CharField(max_length=100, blank=True, verbose_name='المسؤول')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مركز تكلفة'
        verbose_name_plural = 'مراكز التكلفة'

    def __str__(self):
        return f'{self.code} - {self.name}'


class Budget(models.Model):
    PERIOD_CHOICES = [('monthly', 'شهري'), ('quarterly', 'ربع سنوي'), ('yearly', 'سنوي')]
    STATUS_CHOICES = [('draft', 'مسودة'), ('active', 'نشط'), ('closed', 'مغلق')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم الموازنة')
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, verbose_name='الحساب')
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='مركز التكلفة'
    )
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='monthly', verbose_name='الفترة')
    year = models.IntegerField(verbose_name='السنة')
    month = models.IntegerField(null=True, blank=True, verbose_name='الشهر')
    budgeted_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المبلغ المخطط')
    actual_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المبلغ الفعلي')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'موازنة'
        verbose_name_plural = 'الموازنات'
        unique_together = ['account', 'cost_center', 'year', 'month']

    def __str__(self):
        return f'{self.name} - {self.year}'

    @property
    def variance(self):
        return self.actual_amount - self.budgeted_amount

    @property
    def variance_percent(self):
        if self.budgeted_amount:
            return round(((self.actual_amount - self.budgeted_amount) / self.budgeted_amount) * 100, 1)
        return 0
