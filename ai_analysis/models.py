import uuid
from django.db import models
from django.contrib.auth.models import User


class ErrorLog(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'منخفض'),
        ('medium', 'متوسط'),
        ('high', 'عالي'),
        ('critical', 'حرج'),
    ]
    STATUS_CHOICES = [
        ('detected', 'تم الكشف'),
        ('analyzing', 'قيد التحليل'),
        ('resolved', 'تم الحل'),
        ('ignored', 'تجاهل'),
        ('pending', 'بانتظار بيانات'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    error_type = models.CharField(max_length=50, verbose_name='نوع الخطأ')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium', verbose_name='الشدة')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected', db_index=True, verbose_name='الحالة')
    title = models.CharField(max_length=300, verbose_name='العنوان')
    description = models.TextField(verbose_name='الوصف')
    reference_number = models.CharField(max_length=100, blank=True, verbose_name='رقم المرجع')
    affected_account_code = models.CharField(max_length=20, blank=True, verbose_name='الحساب المتأثر')
    affected_account_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الحساب')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='المبلغ')
    entry_date = models.DateField(null=True, blank=True, verbose_name='التاريخ')
    journal_entry_id = models.UUIDField(null=True, blank=True, verbose_name='معرف القيد')
    raw_data = models.JSONField(default=dict, verbose_name='البيانات الأولية')
    ai_analysis = models.TextField(blank=True, verbose_name='تحليل الذكاء الاصطناعي')
    suggested_solution = models.TextField(blank=True, verbose_name='الحل المقترح')
    financial_impact = models.TextField(blank=True, verbose_name='التأثير المحاسبي')
    required_documents = models.TextField(blank=True, verbose_name='المستندات المطلوبة')
    detected_by = models.CharField(max_length=50, default='system', verbose_name='تم الكشف بواسطة')
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='تم الحل بواسطة')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت الحل')
    resolution_notes = models.TextField(blank=True, verbose_name='ملاحظات الحل')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سجل خطأ'
        verbose_name_plural = 'سجلات الأخطاء'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.title}'


class ErrorPattern(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pattern_name = models.CharField(max_length=200, verbose_name='اسم النمط')
    error_type = models.CharField(max_length=50, verbose_name='نوع الخطأ')
    description = models.TextField(verbose_name='الوصف')
    detection_rule = models.JSONField(verbose_name='قاعدة الكشف')
    example = models.TextField(blank=True, verbose_name='مثال')
    suggested_fix = models.TextField(verbose_name='الحل المقترح')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    occurrence_count = models.IntegerField(default=0, verbose_name='عدد التكرار')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'نمط خطأ'
        verbose_name_plural = 'أنماط الأخطاء'

    def __str__(self):
        return self.pattern_name


class Solution(models.Model):
    PRIORITY_CHOICES = [
        (1, 'الأولى'),
        (2, 'الثانية'),
        (3, 'الثالثة'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    error_log = models.ForeignKey(ErrorLog, on_delete=models.CASCADE, related_name='solutions', verbose_name='الخطأ')
    priority = models.IntegerField(choices=PRIORITY_CHOICES, verbose_name='الأولوية')
    title = models.CharField(max_length=300, verbose_name='العنوان')
    description = models.TextField(verbose_name='الوصف')
    steps = models.JSONField(default=list, verbose_name='الخطوات')
    financial_impact = models.TextField(verbose_name='التأثير المحاسبي')
    risk_level = models.CharField(max_length=20, default='low', verbose_name='مستوى المخاطرة')
    requires_approval = models.BooleanField(default=False, verbose_name='يحتاج موافقة')
    applied = models.BooleanField(default=False, verbose_name='تم التطبيق')
    applied_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت التطبيق')
    applied_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='تم التطبيق بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'حل مقترح'
        verbose_name_plural = 'حلول مقترحة'
        ordering = ['priority']

    def __str__(self):
        return f'[{self.get_priority_display()}] {self.title}'
