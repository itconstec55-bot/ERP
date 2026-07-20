import os
import uuid
from django.db import models
from django.conf import settings


class Backup(models.Model):
    BACKUP_TYPES = [
        ('data', 'DB + Media (بيانات)'),
        ('full', 'نسخة كاملة (الكل)'),
        ('json', 'تصدير JSON'),
    ]
    STATUS_CHOICES = [
        ('pending', 'قيد الإنشاء'),
        ('completed', 'مكتملة'),
        ('failed', 'فشل'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم النسخة')
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES, verbose_name='النوع')
    file_path = models.CharField(max_length=500, verbose_name='مسار الملف')
    file_size = models.BigIntegerField(default=0, verbose_name='الحجم (بايت)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name='أنشأها'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'نسخة احتياطية'
        verbose_name_plural = 'النسخ الاحتياطية'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_backup_type_display()})'

    def file_size_display(self):
        size = self.file_size
        if size < 1024:
            return f'{size} B'
        elif size < 1024 * 1024:
            return f'{size / 1024:.1f} KB'
        elif size < 1024 * 1024 * 1024:
            return f'{size / (1024 * 1024):.1f} MB'
        else:
            return f'{size / (1024 * 1024 * 1024):.2f} GB'
    file_size_display.short_description = 'الحجم'

    def delete_file(self):
        if self.file_path and os.path.exists(self.file_path):
            os.remove(self.file_path)
            return True
        return False


class BackupSettings(models.Model):
    auto_backup_enabled = models.BooleanField(default=False, verbose_name='تفعيل النسخ التلقائي')
    backup_interval_hours = models.IntegerField(default=24, verbose_name='فترة النسخ (ساعات)')
    max_backups = models.IntegerField(default=30, verbose_name='الحد الأقصى للنسخ')
    backup_database = models.BooleanField(default=True, verbose_name='نسخ قاعدة البيانات')
    backup_media = models.BooleanField(default=True, verbose_name='نسخ الملفات المرفقة')
    backup_source = models.BooleanField(default=True, verbose_name='نسخ الملفات المصدرية')

    class Meta:
        verbose_name = 'إعدادات النسخ الاحتياطي'
        verbose_name_plural = 'إعدادات النسخ الاحتياطي'

    def __str__(self):
        return 'إعدادات النسخ الاحتياطي'

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class FactoryResetRequest(models.Model):
    """طلب استعادة ضبط المصنع بنظام اعتماد مزدوج (Maker-Checker).

    دورة الحياة:
        pending_approval -> approved -> executing -> completed
        pending_approval -> rejected
        pending_approval | approved -> cancelled
        approved (بعد انتهاء المهلة) -> expired
        executing -> failed
    الحذف الفعلي لا يقع إلا من طبقة الخدمة بعد استيفاء كل الشروط.
    """

    SCOPE_BUSINESS = 'business_data'
    SCOPE_FULL = 'full'
    SCOPE_CHOICES = [
        (SCOPE_BUSINESS, 'بيانات المعاملات فقط (مع الحفاظ على المستخدمين والإعدادات)'),
        (SCOPE_FULL, 'استعادة كاملة (مسح كل البيانات عدا حسابات الدخول)'),
    ]

    STATUS_PENDING = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'
    STATUS_EXECUTING = 'executing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'بانتظار الاعتماد'),
        (STATUS_APPROVED, 'معتمد (بانتظار التنفيذ)'),
        (STATUS_REJECTED, 'مرفوض'),
        (STATUS_CANCELLED, 'ملغى'),
        (STATUS_EXPIRED, 'منتهي الصلاحية'),
        (STATUS_EXECUTING, 'قيد التنفيذ'),
        (STATUS_COMPLETED, 'اكتمل'),
        (STATUS_FAILED, 'فشل التنفيذ'),
    ]

    ACTIVE_STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_EXECUTING)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reason = models.TextField(verbose_name='مبرر الطلب')
    reset_scope = models.CharField(
        max_length=20, choices=SCOPE_CHOICES, default=SCOPE_BUSINESS,
        verbose_name='نطاق الاستعادة')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
        db_index=True, verbose_name='الحالة')

    # --- الطالب (Maker) ---
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='factory_reset_requests', verbose_name='الطالب')
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت الطلب')
    requester_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP الطالب')
    requester_user_agent = models.CharField(max_length=500, blank=True, verbose_name='جهاز الطالب')

    # --- المعتمِد / الرافض (Checker) ---
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='factory_reset_reviews', verbose_name='المعتمِد')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت المراجعة')
    review_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP المعتمِد')
    review_user_agent = models.CharField(max_length=500, blank=True, verbose_name='جهاز المعتمِد')
    review_notes = models.TextField(blank=True, verbose_name='ملاحظات المراجعة')
    approval_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='انتهاء صلاحية الاعتماد')

    # سر التنفيذ لمرة واحدة (يُخزَّن كتجزئة فقط) — يسلّمه المعتمِد للمنفّذ
    execution_token_hash = models.CharField(max_length=64, blank=True, verbose_name='تجزئة رمز التنفيذ')

    # --- المنفّذ (Executor) ---
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='factory_reset_executions', verbose_name='المنفّذ')
    executed_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت التنفيذ')
    execution_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP المنفّذ')
    execution_user_agent = models.CharField(max_length=500, blank=True, verbose_name='جهاز المنفّذ')

    safety_backup = models.ForeignKey(
        Backup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='النسخة الاحتياطية الأمنية')
    result_notes = models.TextField(blank=True, verbose_name='نتيجة التنفيذ')

    class Meta:
        verbose_name = 'طلب استعادة ضبط المصنع'
        verbose_name_plural = 'طلبات استعادة ضبط المصنع'
        ordering = ['-requested_at']
        permissions = [('execute_factory_reset', 'تنفيذ استعادة ضبط المصنع')]

    def __str__(self):
        return f'FactoryReset[{self.get_status_display()}] {self.requested_at:%Y-%m-%d %H:%M}'

    def is_expired(self):
        from django.utils import timezone
        return bool(self.approval_expires_at and timezone.now() > self.approval_expires_at)

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES
