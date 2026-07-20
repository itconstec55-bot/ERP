import uuid

from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile_2fa')
    totp_secret = models.CharField(max_length=64, blank=True, default='', verbose_name='TOTP Secret')
    is_2fa_enabled = models.BooleanField(default=False, verbose_name='المصادقة الثنائية مفعّلة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ملف المستخدم'
        verbose_name_plural = 'ملفات المستخدمين'

    def __str__(self):
        return f'{self.user.username} - 2FA: {"مفعّل" if self.is_2fa_enabled else "معطّل"}'

    @property
    def totp_uri(self):
        if not self.totp_secret:
            return None
        import pyotp

        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(name=self.user.username, issuer_name='نظام المحاسبة')

    def verify_totp(self, code):
        if not self.totp_secret or not self.is_2fa_enabled:
            return False
        import pyotp

        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(code, valid_window=1)

    @classmethod
    def get_or_create_for_user(cls, user):
        profile, created = cls.objects.get_or_create(user=user)
        return profile
