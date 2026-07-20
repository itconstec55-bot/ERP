"""
مهام Celery لمعالجة طابور واتساب
"""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta
from common.whatsapp_service import WhatsAppService
from common.models import WhatsAppMessageQueue
from django.db import models

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_whatsapp_queue(self):
    """مهمة دورية لمعالجة طابور واتساب"""
    service = WhatsAppService()
    try:
        results = service.process_queue(batch_size=50)
        logger.info(f"WhatsApp queue processed: {results}")
        return results
    except Exception as exc:
        logger.exception("Failed to process WhatsApp queue")
        raise self.retry(exc=exc)


@shared_task
def retry_failed_whatsapp_messages():
    """إعادة محاولة الرسائل الفاشلة بعد فترة"""
    service = WhatsAppService()
    
    # البحث عن الرسائل الفاشلة التي لم يتم تجربتها منذ ساعة
    failed_messages = WhatsAppMessageQueue.objects.filter(
        status='failed',
        retry_count__lt=models.F('max_retries'),
        updated_at__lt=timezone.now() - timedelta(hours=1)
    )
    
    processed = 0
    for msg in failed_messages[:20]:  # حد أقصى 20 رسالة في المرة
        msg.status = 'pending'
        msg.retry_count = 0
        msg.save()
        processed += 1
    
    logger.info(f"Reset {processed} failed messages for retry")
    return {'processed': processed}


@shared_task
def cleanup_old_whatsapp_messages():
    """تنظيف الرسائل القديمة من الطابور (أقدم من 30 يوماً)"""
    from django.db.models import Q
    
    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = WhatsAppMessageQueue.objects.filter(
        Q(created_at__lt=cutoff) & 
        Q(status__in=['sent', 'delivered', 'read', 'failed'])
    ).delete()
    
    logger.info(f"Cleaned up {deleted} old WhatsApp messages")
    return {'deleted': deleted}


@shared_task
def send_invoice_whatsapp_task(invoice_id: str, phone: str, party_name: str, party_type: str = "customer"):
    """إرسال فاتورة عبر واتساب كخلفية"""
    from purchases.models import PurchaseInvoice
    from sales.models import SalesInvoice
    
    service = WhatsAppService()
    
    # التحقق من الرقم
    is_valid, result = service.validate_phone_for_whatsapp(phone)
    if not is_valid:
        return {'success': False, 'error': result, 'error_code': 'INVALID_PHONE'}
    
    # تحديد نوع الفاتورة وجلبها
    if party_type == "supplier":
        invoice = PurchaseInvoice.objects.filter(pk=invoice_id).first()
        message_type = "purchase"
    else:
        invoice = SalesInvoice.objects.filter(pk=invoice_id).first()
        message_type = "sales"
    
    if not invoice:
        return {'success': False, 'error': 'Invoice not found', 'error_code': 'NOT_FOUND'}
    
    # تنسيق الرسالة
    message = service.format_invoice_message(invoice, message_type)
    
    # محاولة الإرسال مع إعادة المحاولة
    result = service.send_with_retry(result, message)
    
    if result.success:
        return {'success': True, 'method': 'api', 'message_id': result.message_id}
    
    # حل بديل: wa.me link
    wa_link = WhatsAppService.generate_wa_link(result, message) if hasattr(result, 'phone') else ""
    return {
        'success': True, 
        'method': 'wa.me', 
        'link': wa_link,
        'warning': 'تم استخدام رابط wa.me كحل بديل - الرسالة لم ترسل عبر API'
    }


@shared_task
def send_statement_whatsapp_task(party_id: str, phone: str, party_type: str = "customer"):
    """إرسال كشف حساب عبر واتساب كخلفية"""
    from purchases.models import Supplier
    from sales.models import Customer
    from purchases.models import PurchaseInvoice
    from sales.models import SalesInvoice
    
    service = WhatsAppService()
    
    # التحقق من الرقم
    is_valid, result = service.validate_phone_for_whatsapp(phone)
    if not is_valid:
        return {'success': False, 'error': result, 'error_code': 'INVALID_PHONE'}
    
    # جلب الطرف
    if party_type == "supplier":
        party = Supplier.objects.filter(pk=party_id).first()
        invoices = PurchaseInvoice.objects.filter(supplier=party).order_by('-date') if party else []
    else:
        party = Customer.objects.filter(pk=party_id).first()
        invoices = SalesInvoice.objects.filter(customer=party).order_by('-date') if party else []
    
    if not party:
        return {'success': False, 'error': 'Party not found', 'error_code': 'NOT_FOUND'}
    
    # تنسيق الرسالة
    message = service.format_statement_message(party, invoices, party_type)
    result = service.send_with_retry(result, message)
    
    if result.success:
        return {'success': True, 'method': 'api', 'message_id': result.message_id}
    
    # حل بديل
    wa_link = WhatsAppService.generate_wa_link(result, message) if hasattr(result, 'phone') else ""
    return {
        'success': True, 
        'method': 'wa.me', 
        'link': wa_link,
        'warning': 'تم استخدام رابط wa.me كحل بديل'
    }