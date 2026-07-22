import secrets
import uuid

from django.db import models


class MachineInfo(models.Model):
    MACHINE_TYPES = [
        ('host', 'Host (جهاز رئيسي)'),
        ('client', 'Client (جهاز فرعي)'),
        ('standalone', 'مستقل (بدون ربط)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine_id = models.CharField(max_length=50, unique=True, verbose_name='معرف الجهاز')
    name = models.CharField(max_length=200, verbose_name='اسم الجهاز')
    machine_type = models.CharField(
        max_length=20, choices=MACHINE_TYPES, default='standalone', verbose_name='نوع الجهاز'
    )
    api_key = models.CharField(max_length=64, verbose_name='مفتاح API')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name='آخر مزامنة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'معلومات الجهاز'
        verbose_name_plural = 'معلومات الأجهزة'

    def __str__(self):
        return f'{self.name} ({self.get_machine_type_display()})'

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        if not self.machine_id:
            self.machine_id = f'MACHINE-{secrets.token_hex(4).upper()}'
        super().save(*args, **kwargs)

    def test_connection(self):
        return {
            'machine_id': self.machine_id,
            'name': self.name,
            'machine_type': self.machine_type,
            'is_active': self.is_active,
        }


class SyncLog(models.Model):
    SYNC_TYPES = [('push', 'إرسال'), ('pull', 'استلام'), ('full', 'مزامنة كاملة')]
    STATUS_CHOICES = [('pending', 'قيد التنفيذ'), ('completed', 'مكتملة'), ('failed', 'فشل'), ('partial', 'جزئية')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_machine = models.ForeignKey(
        MachineInfo, on_delete=models.CASCADE, related_name='sync_logs_sent', verbose_name='الجهاز المصدر'
    )
    target_machine = models.ForeignKey(
        MachineInfo,
        on_delete=models.CASCADE,
        related_name='sync_logs_received',
        null=True,
        blank=True,
        verbose_name='الجهاز الهدف',
    )
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES, verbose_name='نوع المزامنة')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    records_sent = models.IntegerField(default=0, verbose_name='السجلات المرسلة')
    records_received = models.IntegerField(default=0, verbose_name='السجلات المستلمة')
    conflicts_found = models.IntegerField(default=0, verbose_name='التعارضات')
    conflicts_resolved = models.IntegerField(default=0, verbose_name='التعارضات المحلولة')
    sync_data = models.JSONField(default=dict, blank=True, verbose_name='بيانات المزامنة')
    error_message = models.TextField(blank=True, verbose_name='رسالة الخطأ')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'سجل المزامنة'
        verbose_name_plural = 'سجلات المزامنة'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.get_sync_type_display()} - {self.get_status_display()} ({self.started_at})'


class SyncSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auto_sync_enabled = models.BooleanField(default=False, verbose_name='تفعيل المزامنة التلقائية')
    sync_interval_minutes = models.IntegerField(default=5, verbose_name='فترة المزامنة (دقائق)')
    sync_on_startup = models.BooleanField(default=True, verbose_name='مزامنة عند التشغيل')
    host_address = models.CharField(max_length=200, blank=True, verbose_name='عنوان Host')
    host_port = models.IntegerField(default=8000, verbose_name='Port Host')
    sync_key = models.CharField(max_length=64, blank=True, verbose_name='مفتاح الربط')

    class Meta:
        verbose_name = 'إعدادات المزامنة'
        verbose_name_plural = 'إعدادات المزامنة'

    def __str__(self):
        return 'إعدادات المزامنة'

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
