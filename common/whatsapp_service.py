"""
خدمة واتساب المحسنة مع:
- Token Refresh تلقائي
- Retry Logic مع Exponential Backoff
- Message Queue للمرسَلات الفاشلة
- Rate Limiting ذكي
- Webhook Handler لتحديثات الحالة
"""

import hashlib
import hmac
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from urllib.parse import quote_plus

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class WhatsAppErrorCode(Enum):
    """رموز أخطاء واتساب موحدة"""

    AUTH_EXPIRED = 'AUTH_EXPIRED'
    RATE_LIMITED = 'RATE_LIMITED'
    INVALID_PHONE = 'INVALID_PHONE'
    MESSAGE_TOO_LONG = 'MESSAGE_TOO_LONG'
    NETWORK_ERROR = 'NETWORK_ERROR'
    API_ERROR = 'API_ERROR'
    WEBHOOK_VERIFICATION_FAILED = 'WEBHOOK_VERIFICATION_FAILED'


class WhatsAppMessageStatus(Enum):
    """حالات رسالة واتساب"""

    PENDING = 'pending'
    QUEUED = 'queued'
    SENT = 'sent'
    DELIVERED = 'delivered'
    READ = 'read'
    FAILED = 'failed'
    EXPIRED = 'expired'


@dataclass
class WhatsAppMessage:
    """نموذج رسالة واتساب"""

    phone: str
    message: str
    message_type: str = 'text'
    metadata: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # 0=عادي، 1=عاجل
    max_retries: int = 3
    created_at: datetime = field(default_factory=timezone.now)
    scheduled_at: datetime | None = None


@dataclass
class WhatsAppAPIResponse:
    """استجابة موحدة لـ API"""

    success: bool
    message_id: str | None = None
    error_code: Optional['WhatsAppErrorCode'] = None
    error_message: str | None = None
    raw_response: dict | None = None
    retry_after: int | None = None  # ثوانٍ للانتظار قبل إعادة المحاولة


class WhatsAppTokenManager:
    """مدير توكن واتساب مع تجديد تلقائي"""

    def __init__(self):
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._app_secret = getattr(settings, 'WHATSAPP_APP_SECRET', None)
        self._app_id = getattr(settings, 'WHATSAPP_APP_ID', None)

    def get_valid_token(self) -> str:
        """الحصول على توكن صالح (مع تجديد تلقائي)"""
        if self._access_token and self._token_expires_at:
            # تجديد قبل 5 دقائق من الانتهاء
            if timezone.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        return self._refresh_token()

    def _refresh_token(self) -> str:
        """تجديد التوكن من Meta"""
        if not self._app_id or not self._app_secret:
            raise ValueError('WHATSAPP_APP_ID و WHATSAPP_APP_SECRET مطلوبان في settings')

        url = 'https://graph.facebook.com/v18.0/oauth/access_token'
        params = {'grant_type': 'client_credentials', 'client_id': self._app_id, 'client_secret': self._app_secret}

        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            raise Exception(f'فشل تجديد التوكن: {response.status_code} - {response.text}')

        data = response.json()
        self._access_token = data['access_token']
        # التوكن ينتهي عادة خلال ساعة، نضع مهلة أمان
        expires_in = data.get('expires_in', 3600)
        self._token_expires_at = timezone.now() + timedelta(seconds=expires_in - 300)

        logger.info('تم تجديد توكن واتساب بنجاح')
        return self._access_token

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> bool:
        """التحقق من توقيع Webhook"""
        if not self._app_secret:
            logger.warning('WHATSAPP_APP_SECRET غير مضبوط - لا يمكن التحقق من Webhook')
            return False

        expected = hmac.new(self._app_secret.encode(), payload, hashlib.sha256).hexdigest()

        # التوقيع يأتي بالشكل: sha256=<hash>
        if not signature_header.startswith('sha256='):
            return False

        provided = signature_header[7:]  # إزالة "sha256="
        return hmac.compare_digest(expected, provided)


class WhatsAppRateLimiter:
    """محدد معدل الإرسال مع دعم الفترات الزمنية"""

    # حدود Meta الافتراضية (قد تتغير)
    LIMITS = {
        'messages_per_second': 80,
        'messages_per_minute': 1000,
        'messages_per_hour': 50000,
        'messages_per_day': 1000000,
    }

    def __init__(self):
        self.prefix = 'whatsapp_ratelimit'

    def check_limit(self, phone: str = None) -> tuple[bool, int | None]:
        """
        التحقق من الحدود المسموحة
        Returns: (allowed, retry_after_seconds)
        """
        now = timezone.now()
        minute_key = f'{self.prefix}:minute:{now.strftime("%Y%m%d%H%M")}'
        hour_key = f'{self.prefix}:hour:{now.strftime("%Y%m%d%H")}'
        day_key = f'{self.prefix}:day:{now.strftime("%Y%m%d")}'

        current_minute = cache.get(minute_key, 0)
        current_hour = cache.get(hour_key, 0)
        current_day = cache.get(day_key, 0)

        if current_minute >= self.LIMITS['messages_per_minute']:
            return False, 60 - now.second

        if current_hour >= self.LIMITS['messages_per_hour']:
            return False, 3600 - (now.minute * 60 + now.second)

        if current_day >= self.LIMITS['messages_per_day']:
            return False, 86400 - (now.hour * 3600 + now.minute * 60 + now.second)

        return True, None

    def increment(self):
        """زيادة العدادات بشكل آمن"""
        now = timezone.now()
        minute_key = f'{self.prefix}:minute:{now.strftime("%Y%m%d%H%M")}'
        hour_key = f'{self.prefix}:hour:{now.strftime("%Y%m%d%H")}'
        day_key = f'{self.prefix}:day:{now.strftime("%Y%m%d")}'

        # استخدام cache.add() للتهيئة الذرّية لمنع Race Condition
        # cache.add() يُعيّن القيمة فقط إذا لم يكن المفتاح موجوداً
        cache.add(minute_key, 0, 60)
        cache.add(hour_key, 0, 3600)
        cache.add(day_key, 0, 86400)

        cache.incr(minute_key)
        cache.incr(hour_key)
        cache.incr(day_key)


from common.models import WhatsAppMessageQueue


class WhatsAppService:
    """
    خدمة واتساب المحسنة مع:
    - Token Refresh تلقائي
    - Retry Logic مع Exponential Backoff
    - Message Queue للمرسَلات الفاشلة
    - Rate Limiting ذكي
    - Webhook Handler
    """

    WHATSAPP_BASE_URL = 'https://wa.me/'
    MAX_MESSAGE_LENGTH = 4096

    # أكواد أخطاء Meta التي لا تتطلب إعادة المحاولة
    NON_RETRYABLE_ERRORS = {
        131000,  # Invalid parameter
        131001,  # Invalid recipient
        131005,  # Message too long
        131042,  # Message expired
        131043,  # Media upload error
    }

    def __init__(self):
        self.token_manager = WhatsAppTokenManager()
        self.rate_limiter = WhatsAppRateLimiter()
        self.api_phone_id = getattr(settings, 'WHATSAPP_PHONE_ID', None)
        self.api_base_url = getattr(settings, 'WHATSAPP_API_BASE_URL', 'https://graph.facebook.com/v18.0')
        self.webhook_verify_token = getattr(settings, 'WHATSAPP_WEBHOOK_VERIFY_TOKEN', None)

    # ==================== Phone Validation ====================

    @staticmethod
    def normalize_phone(phone: str) -> str | None:
        """توحيد صيغة رقم الهاتف"""
        if not phone:
            return None

        digits = re.sub(r'\D', '', phone)

        # السعودية
        if digits.startswith('0'):
            digits = '966' + digits[1:]
        elif digits.startswith('966'):
            pass
        elif len(digits) == 9 and digits.startswith('5'):
            digits = '966' + digits
        elif len(digits) == 10 and digits.startswith('05'):
            digits = '966' + digits[1:]

        if digits.startswith('966') and len(digits) == 12:
            return digits

        # دولي عام
        if 10 <= len(digits) <= 15:
            return digits

        return None

    @classmethod
    def validate_phone_for_whatsapp(cls, phone: str) -> tuple[bool, str | None]:
        normalized = cls.normalize_phone(phone)
        if normalized:
            return True, normalized
        return False, 'رقم الهاتف غير صالح أو غير مدعوم'

    # ==================== Message Formatting ====================

    @staticmethod
    def format_invoice_message(invoice, invoice_type: str = 'sales') -> str:
        """تنسيق رسالة فاتورة لواتساب"""
        from common.decimal_utils import quantize_display

        company_name = getattr(settings, 'COMPANY_NAME', 'شركتنا')

        if invoice_type == 'purchase':
            party = invoice.supplier
            party_name = party.name
            doc_title = 'فاتورة مشتريات'
            doc_ref = f'رقم الفاتورة: {invoice.invoice_number}'
        else:
            party = invoice.customer
            party_name = party.name
            doc_title = 'فاتورة مبيعات'
            doc_ref = f'رقم الفاتورة: {invoice.invoice_number}'

        if invoice.file_number:
            doc_ref += f'\nرقم الملف: {invoice.file_number}'

        # بناء بنود الفاتورة
        lines = invoice.lines.select_related('product').all()
        items_text = ''
        for i, line in enumerate(lines[:5], 1):
            items_text += f'{i}. {line.product.name} - {line.quantity} × {quantize_display(line.unit_price)} = {quantize_display(line.total_price)}\n'
        if lines.count() > 5:
            items_text += f'... و {lines.count() - 5} أصناف أخرى\n'

        message = f"""📋 *{doc_title}*

🏢 *{company_name}*
━━━━━━━━━━━━━━━
👤 *{party_name}*
{doc_ref}
📅 التاريخ: {invoice.date.strftime('%d/%m/%Y')}
━━━━━━━━━━━━━━━
📦 *البنود:*
{items_text}━━━━━━━━━━━━━━━
💰 *المجموع الفرعي:* {quantize_display(invoice.subtotal)} ج.م
📊 *ضريبة VAT (14%):* {quantize_display(invoice.vat_amount)} ج.م
"""

        if invoice.discount_amount > 0:
            message += f'🔻 *الخصم:* {quantize_display(invoice.discount_amount)} ج.م\n'

        if invoice.withholding_tax_amount > 0:
            message += f'📝 *الخصم والتحصيل:* {quantize_display(invoice.withholding_tax_amount)} ج.م\n'

        message += f"""━━━━━━━━━━━━━━━
✅ *الإجمالي:* {quantize_display(invoice.total_amount)} ج.م
💵 *المدفوع:* {quantize_display(invoice.paid_amount)} ج.م
⏳ *المتبقي:* {quantize_display(invoice.remaining_amount)} ج.م
━━━━━━━━━━━━━━━
📌 *الحالة:* {'مرحل' if invoice.is_posted else 'مسودة'}

شكراً لتعاملكم معنا ✨
"""

        # قص الرسالة إذا كانت طويلة
        if len(message) > 4096:
            message = message[:4046] + '\n... [الرسالة مختصرة]'

        return message

    @staticmethod
    def format_statement_message(party, invoices, party_type: str = 'customer') -> str:
        """تنسيق رسالة كشف حساب"""
        from common.decimal_utils import quantize_display

        company_name = getattr(settings, 'COMPANY_NAME', 'شركتنا')

        if party_type == 'supplier':
            party_title = 'المورد'
            balance_label = 'رصيد المورد'
        else:
            party_title = 'العميل'
            balance_label = 'رصيد العميل'

        # حساب الإجماليات
        total_debit = sum(inv.total_amount for inv in invoices if hasattr(inv, 'total_amount'))
        total_paid = sum(inv.paid_amount for inv in invoices if hasattr(inv, 'paid_amount'))
        total_remaining = sum(inv.remaining_amount for inv in invoices if hasattr(inv, 'remaining_amount'))

        message = f"""📊 *كشف حساب {party_title}*

🏢 *{company_name}*
━━━━━━━━━━━━━━━
👤 *{party.name}*
{balance_label}: {quantize_display(party.current_balance)} ج.م
📅 حتى تاريخ: {invoices[0].date.strftime('%d/%m/%Y') if invoices else 'N/A'}
━━━━━━━━━━━━━━━
📋 *الحركات المالية:*
"""

        for inv in invoices[:10]:  # حد 10 فواتير
            status = '✅' if inv.is_posted else '⏳'
            message += f'{status} {inv.invoice_number} | {inv.date.strftime("%d/%m/%Y")} | {quantize_display(inv.total_amount)} | مُدفوع: {quantize_display(inv.paid_amount)} | متبقي: {quantize_display(inv.remaining_amount)}\n'

        if len(invoices) > 10:
            message += f'... و {len(invoices) - 10} فواتير أخرى\n'

        message += f"""━━━━━━━━━━━━━━━
📈 *إجمالي الفواتير:* {quantize_display(total_debit)} ج.م
💵 *إجمالي المدفوع:* {quantize_display(total_paid)} ج.م
⏳ *إجمالي المتبقي:* {quantize_display(total_remaining)} ج.م
━━━━━━━━━━━━━━━
📌 *رصيد الحساب:* {quantize_display(party.current_balance)} ج.م {'(مدين)' if party.current_balance > 0 else '(دائن)'}

شكراً لتعاملكم معنا ✨
"""

        return message

    # ==================== API Sending with Retry Logic ====================

    def send_with_retry(self, phone: str, message: str, max_retries: int = 3) -> WhatsAppAPIResponse:
        """
        إرسال رسالة مع منطق إعادة المحاولة الذكي
        """
        normalized = self.normalize_phone(phone)
        if not normalized:
            return WhatsAppAPIResponse(
                success=False, error_code=WhatsAppErrorCode.INVALID_PHONE, error_message='رقم هاتف غير صالح'
            )

        # فحص معدل الإرسال
        allowed, retry_after = self.rate_limiter.check_limit()
        if not allowed:
            return WhatsAppAPIResponse(
                success=False,
                error_code=WhatsAppErrorCode.RATE_LIMITED,
                error_message=f'تجاوز حد الإرسال. حاول بعد {retry_after} ثانية',
                retry_after=retry_after,
            )

        last_error = None

        for attempt in range(max_retries):
            result = self._send_via_api(normalized, message)

            if result.success:
                self.rate_limiter.increment()
                return result

            last_error = result

            # التحقق من إمكانية إعادة المحاولة
            if not self._should_retry(result, attempt, max_retries):
                break

            # انتظار مع Exponential Backoff + Jitter
            wait_time = self._calculate_backoff(attempt)
            logger.warning(
                f'فشل إرسال واتساب (المحاولة {attempt + 1}/{max_retries}): '
                f'{result.error_message}. إعادة المحاولة بعد {wait_time} ثانية'
            )
            time.sleep(wait_time)

        # جميع المحاولات فشلت - إضافة للطابور
        self._queue_failed_message(phone, message, last_error)

        return last_error

    def _send_via_api(self, phone: str, message: str) -> WhatsAppAPIResponse:
        """إرسال مباشر عبر API"""
        if not self.api_phone_id:
            return WhatsAppAPIResponse(
                success=False,
                error_code=WhatsAppErrorCode.API_ERROR,
                error_message='WhatsApp API غير مهيأ - تحقق من WHATSAPP_PHONE_ID',
            )

        try:
            token = self.token_manager.get_valid_token()

            url = f'{self.api_base_url}/{self.api_phone_id}/messages'
            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
            payload = {'messaging_product': 'whatsapp', 'to': phone, 'type': 'text', 'text': {'body': message}}

            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                message_id = data.get('messages', [{}])[0].get('id')
                return WhatsAppAPIResponse(success=True, message_id=message_id, raw_response=data)

            # معالجة أخطاء API
            error_data = response.json() if response.content else {}
            error_info = error_data.get('error', {})
            error_code = error_info.get('code')
            error_message = error_info.get('message', f'HTTP {response.status_code}')

            # التحقق من انتهاء صلاحية التوكن
            if error_code == 190 or response.status_code == 401:
                self.token_manager._access_token = None  # إجبار التجديد
                return WhatsAppAPIResponse(
                    success=False,
                    error_code=WhatsAppErrorCode.AUTH_EXPIRED,
                    error_message='انتهت صلاحية التوكن',
                    raw_response=error_data,
                )

            # Rate limiting
            if response.status_code == 429 or error_code == 17:
                retry_after = error_data.get('error', {}).get('error_data', {}).get('retry_after', 60)
                return WhatsAppAPIResponse(
                    success=False,
                    error_code=WhatsAppErrorCode.RATE_LIMITED,
                    error_message='تجاوز حد الإرسال',
                    retry_after=retry_after,
                    raw_response=error_data,
                )

            return WhatsAppAPIResponse(
                success=False,
                error_code=WhatsAppErrorCode.API_ERROR,
                error_message=error_message,
                raw_response=error_data,
            )

        except requests.Timeout:
            return WhatsAppAPIResponse(
                success=False,
                error_code=WhatsAppErrorCode.NETWORK_ERROR,
                error_message='انتهت مهلة الاتصال بـ WhatsApp API',
            )
        except requests.RequestException as e:
            return WhatsAppAPIResponse(
                success=False, error_code=WhatsAppErrorCode.NETWORK_ERROR, error_message=f'خطأ شبكة: {str(e)}'
            )
        except Exception as e:
            logger.exception(f'خطأ غير متوقع في إرسال واتساب: {e}')
            return WhatsAppAPIResponse(success=False, error_code=WhatsAppErrorCode.API_ERROR, error_message=str(e))

    def _should_retry(self, result: WhatsAppAPIResponse, attempt: int, max_retries: int) -> bool:
        """تحديد ما إذا كان يجب إعادة المحاولة"""
        if attempt >= max_retries - 1:
            return False

        # لا نعيد المحاولة لأخطاء غير قابلة للإصلاح
        if result.error_code in [WhatsAppErrorCode.INVALID_PHONE, WhatsAppErrorCode.MESSAGE_TOO_LONG]:
            return False

        # لا نعيد المحاولة لأكواد أخطاء Meta غير القابلة للإصلاح
        if result.raw_response:
            error_code = result.raw_response.get('error', {}).get('code')
            if error_code in self.NON_RETRYABLE_ERRORS:
                return False

        return True

    def _calculate_backoff(self, attempt: int) -> float:
        """Exponential Backoff مع Jitter"""
        base = 2**attempt  # 1, 2, 4, 8...
        jitter = random.uniform(0, 1)
        return min(base + jitter, 60)  # حد أقصى 60 ثانية

    def _queue_failed_message(self, phone: str, message: str, error: WhatsAppAPIResponse):
        """إضافة رسالة فاشلة للطابور لإعادة المحاولة لاحقاً"""
        try:
            from common.models import WhatsAppMessageQueue

            WhatsAppMessageQueue.objects.create(
                phone=phone,
                message=message,
                status=WhatsAppMessageStatus.FAILED.value,
                error_message=error.error_message,
                error_code=error.error_code.value if error.error_code else None,
                retry_count=0,
            )
            logger.info(f'تم إضافة رسالة فاشلة للطابور: {phone}')
        except Exception as e:
            logger.error(f'فشل إضافة رسالة للطابور: {e}')

    # ==================== Webhook Handler ====================

    def handle_webhook(self, request) -> dict[str, Any]:
        """
        معالج Webhook لتحديثات حالة الرسائل
        """
        # التحقق من التوقيع
        signature = request.headers.get('X-Hub-Signature-256', '')
        if not self.token_manager.verify_webhook_signature(request.body, signature):
            logger.warning('فشل التحقق من توقيع Webhook')
            return {'success': False, 'error': 'Invalid signature'}

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return {'success': False, 'error': 'Invalid JSON'}

        # معالجة تحديثات حالة الرسائل
        for entry in data.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})

                # تحديثات حالة الرسائل
                for status in value.get('statuses', []):
                    self._handle_status_update(status)

                # رسائل واردة (اختياري)
                for message in value.get('messages', []):
                    self._handle_incoming_message(message)

        return {'success': True}

    def _handle_status_update(self, status: dict):
        """معالجة تحديث حالة الرسالة"""
        message_id = status.get('id')
        status_value = status.get('status')  # sent, delivered, read, failed
        timestamp = status.get('timestamp')
        recipient_id = status.get('recipient_id')

        try:
            msg_queue = WhatsAppMessageQueue.objects.get(meta_message_id=message_id)
            msg_queue.status = status_value
            msg_queue.webhook_data = status

            if status_value == 'sent':
                msg_queue.sent_at = timezone.now()
            elif status_value == 'delivered':
                msg_queue.delivered_at = timezone.now()
            elif status_value == 'failed':
                error_info = status.get('errors', [{}])[0]
                msg_queue.error_message = error_info.get('title', 'فشل الإرسال')
                msg_queue.error_code = str(error_info.get('code', ''))

            msg_queue.save()
            logger.info(f'تم تحديث حالة الرسالة {message_id}: {status_value}')

        except WhatsAppMessageQueue.DoesNotExist:
            logger.warning(f'رسالة غير موجودة في الطابور: {message_id}')

    def _handle_incoming_message(self, message: dict):
        """معالجة رسالة واردة (اختياري)"""
        # يمكن تنفيذ منطق الرد الآلي هنا
        logger.info(f'رسالة واردة من {message.get("from")}: {message.get("text", {}).get("body", "")[:50]}')

    # ==================== Queue Processing ====================

    def process_queue(self, batch_size: int = 50) -> dict[str, int]:
        """
        معالجة طابور الرسائل الفاشلة
        يجب استدعاؤها دورياً (مثلاً عبر Celery Beat)
        """
        pending = WhatsAppMessageQueue.objects.filter(
            status__in=[WhatsAppMessageStatus.FAILED.value, WhatsAppMessageStatus.PENDING.value],
            retry_count__lt=models.F('max_retries'),
        ).order_by('priority', 'created_at')[:batch_size]

        results = {'sent': 0, 'failed': 0, 'skipped': 0}

        for msg in pending:
            # فحص الجدولة
            if msg.scheduled_at and msg.scheduled_at > timezone.now():
                results['skipped'] += 1
                continue

            result = self.send_with_retry(msg.phone, msg.message)

            if result.success:
                msg.status = WhatsAppMessageStatus.SENT.value
                msg.meta_message_id = result.message_id
                msg.sent_at = timezone.now()
                msg.save()
                results['sent'] += 1
            else:
                msg.retry_count += 1
                msg.error_message = result.error_message
                msg.error_code = result.error_code.value if result.error_code else None

                if msg.retry_count >= msg.max_retries:
                    msg.status = WhatsAppMessageStatus.FAILED.value
                else:
                    msg.status = WhatsAppMessageStatus.PENDING.value

                msg.save()
                results['failed'] += 1

        return results

    # ==================== wa.me Fallback ====================

    @staticmethod
    def generate_wa_link(phone: str, message: str) -> str:
        """إنشاء رابط wa.me كحل بديل"""
        normalized = WhatsAppService.normalize_phone(phone)
        if not normalized:
            raise ValueError(f'Invalid phone number: {phone}')

        encoded_message = quote_plus(message)
        return f'{WhatsAppService.WHATSAPP_BASE_URL}{normalized}?text={encoded_message}'


# ==================== دوال مساعدة للاستخدام في Views ====================


def send_invoice_whatsapp(invoice, phone: str, party_name: str, party_type: str = 'customer') -> dict[str, Any]:
    """
    دالة مساعدة لإرسال فاتورة عبر واتساب
    تدعم المحاولات المتكررة والطابور
    """
    service = WhatsAppService()

    # التحقق من الرقم
    is_valid, normalized = service.validate_phone_for_whatsapp(phone)
    if not is_valid:
        return {'success': False, 'error': normalized, 'error_code': 'INVALID_PHONE'}

    # تنسيق الرسالة
    message = service.format_invoice_message(invoice, 'purchase' if party_type == 'supplier' else 'sales')

    # محاولة الإرسال مع إعادة المحاولة
    api_result = service.send_with_retry(normalized, message)

    if api_result.success:
        return {'success': True, 'method': 'api', 'message_id': api_result.message_id}

    # حل بديل: wa.me link
    wa_link = WhatsAppService.generate_wa_link(normalized, message)
    return {
        'success': True,
        'method': 'wa.me',
        'link': wa_link,
        'warning': 'تم استخدام رابط wa.me كحل بديل - الرسالة لم ترسل عبر API',
    }


def send_statement_whatsapp(party, invoices, phone: str, party_type: str = 'customer') -> dict[str, Any]:
    """إرسال كشف حساب عبر واتساب"""
    service = WhatsAppService()

    is_valid, normalized = service.validate_phone_for_whatsapp(phone)
    if not is_valid:
        return {'success': False, 'error': normalized, 'error_code': 'INVALID_PHONE'}

    message = service.format_statement_message(party, invoices, party_type)
    api_result = service.send_with_retry(normalized, message)

    if api_result.success:
        return {'success': True, 'method': 'api', 'message_id': api_result.message_id}

    wa_link = WhatsAppService.generate_wa_link(normalized, message)
    return {'success': True, 'method': 'wa.me', 'link': wa_link, 'warning': 'تم استخدام رابط wa.me كحل بديل'}
