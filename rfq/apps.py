from django.apps import AppConfig


class RfqConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rfq'
    label = 'rfq'
    verbose_name = 'عروض الأسعار'

    def ready(self):
        from django.db.models.signals import post_save, post_delete
        from .models import RFQ, RFQLine, Quotation, QuotationLine
        from audit.models import log_action
        from audit.context import get_current_user

        AUDITED = [RFQ, RFQLine, Quotation, QuotationLine]

        def _post_save(sender, instance, created, **kwargs):
            action = 'create' if created else 'update'
            log_action(
                get_current_user(),
                action,
                instance._meta.label,
                object_id=instance.pk,
                object_repr=str(instance)[:200],
            )

        def _post_delete(sender, instance, **kwargs):
            log_action(
                get_current_user(),
                'delete',
                instance._meta.label,
                object_id=instance.pk,
                object_repr=str(instance)[:200],
            )

        for model_cls in AUDITED:
            label = model_cls._meta.label_lower
            post_save.connect(_post_save, sender=model_cls, dispatch_uid=f'rfq_save_{label}')
            post_delete.connect(_post_delete, sender=model_cls, dispatch_uid=f'rfq_del_{label}')

        from django.contrib.auth import get_user_model
        from notifications.models import NotificationLog

        _last_status = {}

        def _notify(recipients, subject, body):
            for u in recipients:
                if u.email:
                    NotificationLog.objects.create(
                        template=None, recipient_email=u.email,
                        subject=subject, body=body, success=True,
                    )

        def _rfq_post_save(sender, instance, created, **kwargs):
            target = 'sent'
            prev = _last_status.get(instance.pk)
            _last_status[instance.pk] = instance.status
            if instance.status == target and prev != target:
                superusers = get_user_model().objects.filter(is_superuser=True)
                _notify(
                    superusers,
                    'طلب عروض أسعار بانتظار الرد',
                    f'طلب عروض الأسعار {instance.number} أُرسل ويحتاج متابعة العروض.',
                )

        post_save.connect(
            _rfq_post_save, sender='rfq.RFQ',
            dispatch_uid='rfq_notify_sent',
        )
