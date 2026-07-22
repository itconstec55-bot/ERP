import uuid

from django.db import models


class RecurringJournal(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'يومي'),
        ('weekly', 'أسبوعي'),
        ('monthly', 'شهري'),
        ('quarterly', 'ربع سنوي'),
        ('yearly', 'سنوي'),
    ]
    STATUS_CHOICES = [('active', 'نشط'), ('paused', 'متوقف'), ('completed', 'مكتمل')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='الاسم')
    description = models.TextField(blank=True, verbose_name='الوصف')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, verbose_name='التكرار')
    day_of_month = models.IntegerField(default=1, verbose_name='يوم الشهر')
    next_due_date = models.DateField(verbose_name='التاريخ التالي')
    journal_type = models.CharField(
        max_length=20,
        choices=[('general', 'قيد عام'), ('receipt', 'قبض'), ('payment', 'صرف')],
        default='general',
        verbose_name='نوع القيد',
    )
    reference = models.CharField(max_length=100, blank=True, verbose_name='المرجع')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='الحالة')
    total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='إجمالي المدين')
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='إجمالي الدائن')
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'قيد دوري'
        verbose_name_plural = 'قيود دورية'

    def __str__(self):
        return f'{self.name} ({self.get_frequency_display()})'


class RecurringJournalLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal = models.ForeignKey(RecurringJournal, on_delete=models.CASCADE, related_name='lines', verbose_name='القيد')
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, verbose_name='الحساب')
    description = models.CharField(max_length=300, blank=True, verbose_name='البيان')
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المدين')
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='الدائن')

    class Meta:
        verbose_name = 'بند قيد دوري'
        verbose_name_plural = 'بنود قيد دوري'

    def __str__(self):
        return f'{self.account} - {self.debit}/{self.credit}'


class RecurringJournalLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal = models.ForeignKey(RecurringJournal, on_delete=models.CASCADE, related_name='logs', verbose_name='القيد')
    executed_date = models.DateField(verbose_name='تاريخ التنفيذ')
    journal_entry = models.ForeignKey(
        'accounts.JournalEntry', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القيد المرتبط'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سجل تنفيذ قيد دوري'
        verbose_name_plural = 'سجلات تنفيذ القيود الدورية'
