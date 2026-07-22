from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = 'سجل التدقيق'

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from .context import get_current_user
        from .models import log_action

        AUDITED = [
            'accounts.journalentry',
            'accounts.journalentryline',
            'accounts.account',
            'payment_receipts.paymentreceipt',
            'payment_receipts.receipt',
            'purchases.purchaseinvoice',
            'purchases.purchaseinvoiceline',
            'purchases.supplier',
            'sales.salesinvoice',
            'sales.salesinvoiceline',
            'sales.customer',
            'cheques.cheque',
            'treasury.banktransaction',
            'treasury.safetransaction',
            'tax_invoices.taxinvoice',
            'requisitions.requisition',
            'requisitions.requisitionline',
            'rfq.rfq',
            'rfq.rfqline',
            'rfq.quotation',
            'rfq.quotationline',
            'purchase_orders.purchaseorder',
            'purchase_orders.purchaseorderline',
            'goods_received.goodsreceivednote',
            'goods_received.goodsreceivednoteline',
            'warehouses.warehouseproduct',
            'budget.costcenter',
            'budget.budget',
            'warehouses.warehouse',
            'company.companybranch',
            'accounts.accounttype',
            'common.userprofile',
            'access_control.role',
            'access_control.rolescreenpermission',
            'access_control.userscreenpermission',
            'access_control.userroleassignment',
            'access_control.userbranch',
            'access_control.userwarehouse',
            'access_control.useraccounttypescope',
        ]

        def _get_label(instance):
            return instance._meta.label

        def _post_save(sender, instance, created, **kwargs):
            label = _get_label(instance)
            if label.lower() not in AUDITED:
                return
            action = 'create' if created else 'update'
            log_action(get_current_user(), action, label, object_id=instance.pk, object_repr=str(instance)[:200])

        def _post_delete(sender, instance, **kwargs):
            label = _get_label(instance)
            if label.lower() not in AUDITED:
                return
            log_action(get_current_user(), 'delete', label, object_id=instance.pk, object_repr=str(instance)[:200])

        for label in AUDITED:
            app, model = label.split('.')
            from django.apps import apps as django_apps

            try:
                model_cls = django_apps.get_model(app, model)
            except LookupError:
                continue
            post_save.connect(_post_save, sender=model_cls, dispatch_uid=f'audit_save_{label}')
            post_delete.connect(_post_delete, sender=model_cls, dispatch_uid=f'audit_del_{label}')
