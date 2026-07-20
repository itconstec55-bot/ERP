from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Requisition, RequisitionLine


@receiver(post_save, sender=Requisition)
def _audit_requisition_save(sender, instance, created, **kwargs):
    from audit.models import log_action

    log_action(
        None,
        'create' if created else 'update',
        'requisitions.requisition',
        object_id=instance.pk,
        object_repr=str(instance),
    )


@receiver(post_delete, sender=Requisition)
def _audit_requisition_delete(sender, instance, **kwargs):
    from audit.models import log_action

    log_action(None, 'delete', 'requisitions.requisition', object_id=instance.pk, object_repr=str(instance))


@receiver(post_save, sender=RequisitionLine)
def _audit_requisition_line_save(sender, instance, created, **kwargs):
    from audit.models import log_action

    log_action(
        None,
        'create' if created else 'update',
        'requisitions.requisitionline',
        object_id=instance.pk,
        object_repr=str(instance),
    )


@receiver(post_delete, sender=RequisitionLine)
def _audit_requisition_line_delete(sender, instance, **kwargs):
    from audit.models import log_action

    log_action(None, 'delete', 'requisitions.requisitionline', object_id=instance.pk, object_repr=str(instance))
