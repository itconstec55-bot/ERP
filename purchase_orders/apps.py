from django.apps import AppConfig


class PurchaseOrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'purchase_orders'
    verbose_name = 'أوامر الشراء'

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from notifications.models import NotificationLog

        _last_status = {}

        def _notify(recipients, subject, body):
            for u in recipients:
                if u.email:
                    NotificationLog.objects.create(
                        template=None, recipient_email=u.email, subject=subject, body=body, success=True
                    )

        def _po_post_save(sender, instance, created, **kwargs):
            target = 'approved'
            prev = _last_status.get(instance.pk)
            _last_status[instance.pk] = instance.status
            if instance.status == target and prev != target:
                recipients = list(get_user_model().objects.filter(is_superuser=True))
                if instance.created_by and instance.created_by.email:
                    recipients.append(instance.created_by)
                _notify(recipients, 'تم اعتماد أمر شراء', f'تم اعتماد أمر الشراء {instance.order_number}.')

        post_save.connect(
            _po_post_save, sender='purchase_orders.PurchaseOrder', dispatch_uid='purchase_orders_notify_approved'
        )
