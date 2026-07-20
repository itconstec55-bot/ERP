import uuid
from django.db import models
from django.conf import settings


class NotificationCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='الاسم')
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    class Meta:
        verbose_name = 'فئة الإشعار'
        verbose_name_plural = 'فئات الإشعارات'

    def __str__(self):
        return self.name


class NotificationTemplate(models.Model):
    EVENT_CHOICES = [
        ('invoice_created', 'إنشاء فاتورة مبيعات'),
        ('invoice_posted', 'ترحيل فاتورة مبيعات'),
        ('invoice_overdue', 'فاتورة مبيعات متأخرة'),
        ('low_stock', 'مخزون منخفض'),
        ('salary_due', 'موعد صرف رواتب'),
        ('backup_completed', 'اكتمال النسخ الاحتياطي'),
        ('reconciliation_needed', 'حاجة تسوية بنكية'),
        ('document_expiring', 'وثيقة تنتهي صلاحيتها'),
        ('purchase_invoice_created', 'إنشاء فاتورة مشتريات'),
        ('purchase_invoice_posted', 'ترحيل فاتورة مشتريات'),
        ('contractor_payment_created', 'إنشاء دفعة مقاول'),
        ('contractor_payment_posted', 'ترحيل دفعة مقاول'),
        ('supplier_credit_exceeded', 'تجاوز حد ائتمان المورد'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='الاسم')
    event = models.CharField(max_length=50, choices=EVENT_CHOICES, unique=True, verbose_name='الحدث')
    subject_template = models.CharField(max_length=200, verbose_name='قالب الموضوع')
    body_template = models.TextField(verbose_name='قالب المحتوى')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, verbose_name='المستلمون')

    class Meta:
        verbose_name = 'قالب إشعار'
        verbose_name_plural = 'قوالب الإشعارات'

    def __str__(self):
        return f'{self.name} ({self.get_event_display()})'


class NotificationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, verbose_name='القالب')
    recipient_email = models.EmailField(verbose_name='البريد للمستلم')
    subject = models.CharField(max_length=200, verbose_name='الموضوع')
    body = models.TextField(verbose_name='المحتوى')
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True, verbose_name='نجاح')
    error_message = models.TextField(blank=True, verbose_name='رسالة الخطأ')

    class Meta:
        verbose_name = 'سجل إشعار'
        verbose_name_plural = 'سجلات الإشعارات'
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.subject} - {self.recipient_email}'
