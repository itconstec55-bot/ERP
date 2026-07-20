import logging
from django.core.mail import send_mail
from django.conf import settings as django_settings
from .models import NotificationTemplate, NotificationLog

logger = logging.getLogger('accounting')


def render_template(template_text, context):
    """استبدال المتغيرات في القالب."""
    if not template_text:
        return ''
    result = template_text
    for key, value in context.items():
        result = result.replace('{{' + key + '}}', str(value))
    return result


def send_notification(event, context=None, extra_recipients=None):
    """
    إرسال إشعار بالبريد الإلكتروني.
    
    event: نوع الحدث (invoice_created, invoice_posted, low_stock, etc.)
    context: قاموس المتغيرات للاستبدال في القالب
    extra_recipients: قائمة إضافية بالبريد الإلكتروني
    """
    if context is None:
        context = {}
    if extra_recipients is None:
        extra_recipients = []

    template = NotificationTemplate.objects.filter(event=event, is_active=True).first()
    if not template:
        logger.debug('No active template for event: %s', event)
        return False

    subject = render_template(template.subject_template, context)
    body = render_template(template.body_template, context)

    recipients = set(extra_recipients)
    for user in template.recipients.filter(is_active=True, email__isnull=False):
        if user.email:
            recipients.add(user.email)

    if not recipients:
        logger.warning('No recipients for notification event: %s', event)
        return False

    email_host_user = getattr(django_settings, 'EMAIL_HOST_USER', '')
    if not email_host_user:
        logger.warning('EMAIL_HOST_USER not configured. Skipping email send.')
        _log_notification(template, '', subject, body, success=False,
                          error_message='EMAIL_HOST_USER not configured')
        return False

    success_count = 0
    for email in recipients:
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=email_host_user,
                recipient_list=[email],
                fail_silently=False,
            )
            _log_notification(template, email, subject, body, success=True)
            success_count += 1
        except Exception as e:
            _log_notification(template, email, subject, body, success=False, error_message=str(e))
            logger.exception('Failed to send notification to %s', email)

    return success_count > 0


def _log_notification(template, recipient_email, subject, body, success=True, error_message=''):
    NotificationLog.objects.create(
        template=template,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        success=success,
        error_message=error_message,
    )


def notify_invoice_created(invoice):
    context = {
        'invoice_number': invoice.invoice_number,
        'customer_name': invoice.customer.name if invoice.customer else '',
        'total_amount': f'{invoice.total_amount:,.2f}',
        'date': str(invoice.date),
    }
    send_notification('invoice_created', context)


def notify_invoice_posted(invoice):
    context = {
        'invoice_number': invoice.invoice_number,
        'customer_name': invoice.customer.name if invoice.customer else '',
        'total_amount': f'{invoice.total_amount:,.2f}',
        'date': str(invoice.date),
    }
    send_notification('invoice_posted', context)


def notify_low_stock(product, current_stock, minimum_stock):
    context = {
        'product_name': product.name,
        'product_code': product.code,
        'current_stock': str(current_stock),
        'minimum_stock': str(minimum_stock),
    }
    send_notification('low_stock', context)


def notify_salary_due():
    send_notification('salary_due', {
        'message': 'موعد صرف الرواتب الشهرية',
    })


def notify_purchase_invoice_created(invoice):
    context = {
        'invoice_number': invoice.invoice_number,
        'supplier_name': invoice.supplier.name if invoice.supplier else '',
        'total_amount': f'{invoice.total_amount:,.2f}',
        'date': str(invoice.date),
    }
    send_notification('purchase_invoice_created', context)


def notify_purchase_invoice_posted(invoice):
    context = {
        'invoice_number': invoice.invoice_number,
        'supplier_name': invoice.supplier.name if invoice.supplier else '',
        'total_amount': f'{invoice.total_amount:,.2f}',
        'date': str(invoice.date),
    }
    send_notification('purchase_invoice_posted', context)


def notify_contractor_payment_created(payment):
    context = {
        'payment_number': payment.payment_number,
        'contractor_name': payment.contract.contractor.name if payment.contract and payment.contract.contractor else '',
        'contract_number': payment.contract.contract_number if payment.contract else '',
        'amount': f'{payment.amount:,.2f}',
        'date': str(payment.payment_date),
    }
    send_notification('contractor_payment_created', context)


def notify_contractor_payment_posted(payment):
    context = {
        'payment_number': payment.payment_number,
        'contractor_name': payment.contract.contractor.name if payment.contract and payment.contract.contractor else '',
        'amount': f'{payment.amount:,.2f}',
        'date': str(payment.payment_date),
    }
    send_notification('contractor_payment_posted', context)


def notify_supplier_credit_exceeded(supplier, current_balance, credit_limit):
    context = {
        'supplier_name': supplier.name,
        'current_balance': f'{current_balance:,.2f}',
        'credit_limit': f'{credit_limit:,.2f}',
    }
    send_notification('supplier_credit_exceeded', context)
