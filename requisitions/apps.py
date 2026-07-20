from django.apps import AppConfig


class RequisitionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'requisitions'
    verbose_name = 'طلبات الشراء'

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from notifications.models import NotificationLog

        from . import signals  # noqa: F401

        _last_status = {}

        def _notify(recipients, subject, body):
            for u in recipients:
                if u.email:
                    NotificationLog.objects.create(
                        template=None, recipient_email=u.email, subject=subject, body=body, success=True
                    )

        def _requisition_post_save(sender, instance, created, **kwargs):
            target = 'pending'
            prev = _last_status.get(instance.pk)
            _last_status[instance.pk] = instance.status
            if instance.status == target and prev != target:
                superusers = get_user_model().objects.filter(is_superuser=True)
                _notify(superusers, 'طلب شراء بانتظار الاعتماد', f'طلب الشراء {instance.number} بانتظار اعتمادك.')

        post_save.connect(
            _requisition_post_save, sender='requisitions.Requisition', dispatch_uid='requisitions_notify_pending'
        )
