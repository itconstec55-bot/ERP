from django.apps import AppConfig


class AccessControlConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'access_control'
    verbose_name = 'إدارة الصلاحيات'

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from . import models as m
        from .resolver import bump_global_version, invalidate_user

        def _bump(sender, instance, **kwargs):
            bump_global_version()

        def _invalidate_user(sender, instance, **kwargs):
            uid = getattr(instance, 'user_id', None)
            if uid:
                invalidate_user(uid)

        role_scoped = [m.Role, m.RoleScreenPermission, m.Screen]
        user_scoped = [
            m.UserScreenPermission,
            m.UserRoleAssignment,
            m.UserBranch,
            m.UserWarehouse,
            m.UserAccountTypeScope,
        ]

        for model_cls in role_scoped:
            post_save.connect(_bump, sender=model_cls, dispatch_uid=f'ac_bump_save_{model_cls.__name__}')
            post_delete.connect(_bump, sender=model_cls, dispatch_uid=f'ac_bump_del_{model_cls.__name__}')

        for model_cls in user_scoped:
            post_save.connect(_invalidate_user, sender=model_cls, dispatch_uid=f'ac_inv_save_{model_cls.__name__}')
            post_delete.connect(_invalidate_user, sender=model_cls, dispatch_uid=f'ac_inv_del_{model_cls.__name__}')

        from common.models import UserProfile

        def _invalidate_profile(sender, instance, **kwargs):
            uid = getattr(instance, 'user_id', None)
            if uid:
                invalidate_user(uid)

        post_save.connect(_invalidate_profile, sender=UserProfile, dispatch_uid='ac_inv_save_UserProfile')
        post_delete.connect(_invalidate_profile, sender=UserProfile, dispatch_uid='ac_inv_del_UserProfile')
