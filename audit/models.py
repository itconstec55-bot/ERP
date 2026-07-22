import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'إنشاء'),
        ('update', 'تعديل'),
        ('delete', 'حذف'),
        ('login', 'دخول'),
        ('export', 'تصدير'),
        ('import', 'استيراد'),
        ('post', 'ترحيل'),
        ('reverse', 'عكس'),
        ('backup', 'نسخ احتياطي'),
        ('sync', 'مزامنة'),
        ('access_denied', 'رفض وصول'),
        ('permission_change', 'تغيير صلاحية'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, db_index=True, verbose_name='المستخدم'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True, verbose_name='الإجراء')
    model_name = models.CharField(max_length=100, db_index=True, verbose_name='النموذج')
    object_id = models.CharField(max_length=100, blank=True, verbose_name='معرف السجل')
    object_repr = models.CharField(max_length=200, verbose_name='وصف السجل')
    changes = models.JSONField(default=dict, blank=True, verbose_name='التغييرات')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='عنوان IP')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='المتصفح')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='التاريخ والوقت')

    class Meta:
        verbose_name = 'سجل تدقيق'
        verbose_name_plural = 'سجلات التدقيق'
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['model_name', 'action'], name='audit_model_action_idx')]

    def __str__(self):
        return f'{self.get_action_display()} - {self.model_name} ({self.timestamp})'


def log_action(user, action, model_name, object_id='', object_repr='', changes=None, request=None):
    from .context import get_current_user

    if user is None and request is not None:
        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
    if user is None:
        user = get_current_user()
    ip = None
    ua = ''
    if request:
        ip = request.META.get('REMOTE_ADDR')
        ua = request.META.get('HTTP_USER_AGENT', '')[:500]
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        object_repr=str(object_repr)[:200],
        changes=changes or {},
        ip_address=ip,
        user_agent=ua,
    )
