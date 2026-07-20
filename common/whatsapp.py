"""
خدمة واتساب موحدة لنظام المحاسبة
تدعم الإرسال عبر رابط wa.me أو API رسمي
تدعم الأرقام السعودية والمصرية
"""

import re
import urllib.parse
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone


class WhatsAppService:
    """
    خدمة موحدة لإرسال رسائل واتساب
    تدعم طريقتين:
    1. رابط wa.me (لا يحتاج إعدادات، يفتح في المتصفح/التطبيق)
    2. WhatsApp Business API (يحتاج token وإعدادات)
    """

    # أنماط أرقام الهواتف المدعومة
    # السعودية: جوال يبدأ بـ 5 (9665xxxxxxxx)
    SAUDI_MOBILE_PATTERN = re.compile(r'^(\+?966|0)?5\d{8}$')
    # المصرية: جوال يبدأ بـ 10، 11، 12، 15 (2010xxxxxxxx، 2011xxxxxxxx، إلخ)
    EGYPT_MOBILE_PATTERN = re.compile(r'^(\+?20|0)?1[0125]\d{8}$')
    # أرضي: كود منطقة (02، 03، إلخ) + رقم (7-8 أرقام)
    EGYPT_LANDLINE_PATTERN = re.compile(r'^(\+?20|0)?[23456789]\d{7,8}$')

    def __init__(self):
        self.api_token = getattr(settings, 'WHATSAPP_API_TOKEN', None)
        self.api_phone_id = getattr(settings, 'WHATSAPP_API_PHONE_ID', None)
        self.api_url = f"https://graph.facebook.com/v18.0/{self.api_phone_id}/messages" if self.api_phone_id else None

    @staticmethod
    def clean_phone_number(phone: str) -> str:
        """تنظيف رقم الهاتف وإرجاعه بالصيغة الدولية"""
        if not phone:
            return ""

        # إزالة جميع الرموز غير الرقمية
        digits = re.sub(r'\D', '', phone)

        # التعامل مع الأرقام السعودية
        if digits.startswith('966'):
            return digits
        elif digits.startswith('05') and len(digits) == 10:
            return '966' + digits[1:]
        elif digits.startswith('5') and len(digits) == 9:
            return '966' + digits
        elif digits.startswith('00966'):
            return digits[2:]  # إزالة 00
        elif len(digits) == 10 and digits.startswith('5'):
            return '966' + digits[1:]

        # التعامل مع الأرقام المصرية
        if digits.startswith('20'):
            return digits
        elif digits.startswith('01') and len(digits) == 11 and digits[2] in '0125':
            # جوال مصري: 010، 011، 012، 015 + 8 أرقام
            return '20' + digits[1:]
        elif digits.startswith('1') and len(digits) == 10 and digits[1] in '0125':
            # جوال مصري بدون صفر: 10xxxxxxxx، 11xxxxxxxx، إلخ
            return '20' + digits
        elif digits.startswith('0020'):
            return digits[2:]  # إزالة 00
        elif digits.startswith('02') and len(digits) >= 9:
            # أرضي القاهرة/الجيزة: 02 + 7-8 أرقام
            return '20' + digits[1:]
        elif digits.startswith('03') and len(digits) >= 9:
            # أرضي الإسكندرية: 03 + 7-8 أرقام
            return '20' + digits[1:]
        elif digits.startswith('0') and len(digits) >= 9:
            # باقي المحافظات: كود منطقة يبدأ بـ 0 + رقم (7+ أرقام)
            return '20' + digits[1:]

        return digits

    @classmethod
    def validate_phone_for_whatsapp(cls, phone: str) -> tuple[bool, str]:
        """
        التحقق من صلاحية رقم الهاتف للواتساب
        إرجاع: (is_valid, cleaned_phone_or_error_message)
        """
        if not phone:
            return False, "رقم الهاتف فارغ"

        cleaned = cls.clean_phone_number(phone)

        # التحقق من الأنماط المدعومة
        # نحتاج لاختبار الرقم بالصيغة المحلية (بالبادئة 0)
        # استخراج البادئة الدولية فقط
        if cleaned.startswith('966'):
            local_format = '0' + cleaned[3:]
            if cls.SAUDI_MOBILE_PATTERN.match(local_format):
                return True, cleaned
        elif cleaned.startswith('20'):
            local_format = '0' + cleaned[2:]
            if cls.EGYPT_MOBILE_PATTERN.match(local_format) or cls.EGYPT_LANDLINE_PATTERN.match(local_format):
                return True, cleaned

        return False, f"رقم الهاتف غير صالح للواتساب: {phone}"

    @staticmethod
    def generate_wa_link(phone: str, message: str) -> str:
        """
        إنشاء رابط wa.me للرسالة
        phone: رقم الهاتف بالصيغة الدولية (966xxxxxxxxx)
        message: نص الرسالة (سيتم ترميزه URL)
        """
        encoded_message = urllib.parse.quote(message)
        return f"https://wa.me/{phone}?text={encoded_message}"

    def send_via_api(self, phone: str, message: str) -> Dict[str, Any]:
        """
        إرسال عبر WhatsApp Business API الرسمي
        يتطلب: WHATSAPP_API_TOKEN و WHATSAPP_API_PHONE_ID في settings
        """
        if not self.api_token or not self.api_phone_id:
            return {'success': False, 'error': 'WhatsApp API غير مهيأ - تحقق من الإعدادات'}

        try:
            import requests

            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": message}
            }

            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }

            response = requests.post(self.api_url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                return {'success': True, 'response': response.json()}
            else:
                return {'success': False, 'error': f'API Error {response.status_code}: {response.text}'}

        except ImportError:
            return {'success': False, 'error': 'مكتبة requests غير مثبتة'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def format_invoice_message(invoice, party_name: str, party_type: str = "customer") -> str:
        """
        تنسيق رسالة فاتورة جاهزة للإرسال
        party_type: 'customer' للمبيعات، 'supplier' للمشتريات
        """
        invoice_type = "مبيعات" if party_type == "customer" else "مشتريات"
        party_label = "العميل" if party_type == "customer" else "المورد"

        lines = [
            f"📄 *فاتورة {invoice_type}*",
            f"📌 رقم الفاتورة: {invoice.invoice_number}",
            f"🔖 رقم الملف: {invoice.file_number or 'غير محدد'}",
            f"👤 {party_label}: {party_name}",
            f"📅 التاريخ: {invoice.date.strftime('%d/%m/%Y')}",
            "",
            "📋 *التفاصيل المالية:*",
            f"• المبلغ قبل الضريبة: {invoice.subtotal:,.2f} ج.م",
        ]

        if hasattr(invoice, 'vat_amount') and invoice.vat_amount:
            lines.append(f"• ضريبة القيمة المضافة (14%): {invoice.vat_amount:,.2f} ج.م")

        if hasattr(invoice, 'discount_amount') and invoice.discount_amount:
            lines.append(f"• الخصم: {invoice.discount_amount:,.2f} ج.م")

        if hasattr(invoice, 'withholding_tax_amount') and invoice.withholding_tax_amount:
            lines.append(f"• الخصم والتحصيل: {invoice.withholding_tax_amount:,.2f} ج.م")

        lines.extend([
            f"• *الإجمالي: {invoice.total_amount:,.2f} ج.م*",
            "",
        ])

        if hasattr(invoice, 'paid_amount'):
            lines.extend([
                f"💰 المحصل/المدفوع: {invoice.paid_amount:,.2f} ج.م",
                f"⏳ المتبقي: {invoice.remaining_amount:,.2f} ج.م",
                "",
            ])

        lines.append("📍 *نظام تواريدات المحاسبي*")
        lines.append(f"⏰ {timezone.now().strftime('%d/%m/%Y %H:%M')}")

        return "\n".join(lines)

    @staticmethod
    def format_statement_message(party, invoices, party_type: str = "customer") -> str:
        """
        تنسيق رسالة كشف حساب
        party: Customer أو Supplier
        invoices: queryset من الفواتير
        party_type: 'customer' أو 'supplier'
        """
        party_label = "عميل" if party_type == "customer" else "مورد"
        invoice_label = "مبيعات" if party_type == "customer" else "مشتريات"

        total_amount = sum(inv.total_amount for inv in invoices)
        total_paid = sum(inv.paid_amount for inv in invoices if hasattr(inv, 'paid_amount'))
        total_remaining = sum(inv.remaining_amount for inv in invoices if hasattr(inv, 'remaining_amount'))

        lines = [
            f"📊 *كشف حساب {party_label}*",
            f"👤 الاسم: {party.name}",
            f"📞 الهاتف: {party.mobile or party.phone or 'غير مسجل'}",
            f"🔖 رقم الملف: {getattr(party, 'file_number', 'غير محدد') or 'غير محدد'}",
            "",
            f"📋 *ملخص فواتير {invoice_label}:*",
            f"• عدد الفواتير: {invoices.count()}",
            f"• إجمالي المبالغ: {total_amount:,.2f} ج.م",
            f"• إجمالي المدفوع/المحصّل: {total_paid:,.2f} ج.م",
            f"• *إجمالي المتبقي: {total_remaining:,.2f} ج.م*",
            "",
            "📝 *تفاصيل الفواتير:*",
        ]

        for inv in invoices[:15]:  # أول 15 فاتورة فقط لتجنب طول الرسالة
            status = "✅" if getattr(inv, 'is_posted', False) else "⏳"
            lines.append(
                f"{status} {inv.invoice_number} | "
                f"{inv.date.strftime('%d/%m/%Y')} | "
                f"إجمالي: {inv.total_amount:,.2f} | "
                f"متبقي: {getattr(inv, 'remaining_amount', 0):,.2f}"
            )

        if invoices.count() > 15:
            lines.append(f"... و {invoices.count() - 15} فاتورة أخرى")

        lines.extend([
            "",
            "📍 *نظام تواريدات المحاسبي*",
            f"⏰ {timezone.now().strftime('%d/%m/%Y %H:%M')}",
        ])

        return "\n".join(lines)


# دالة مساعدة سريعة للاستخدام في Views
def send_invoice_whatsapp(invoice, phone: str, party_name: str, party_type: str = "customer") -> Dict[str, Any]:
    """
    دالة مساعدة لإرسال فاتورة عبر واتساب
    تستخدم في Views مباشرة
    """
    service = WhatsAppService()

    # التحقق من الرقم
    is_valid, result = service.validate_phone_for_whatsapp(phone)
    if not is_valid:
        return {'success': False, 'error': result}

    # تنسيق الرسالة
    message = service.format_invoice_message(invoice, party_name, party_type)

    # محاولة الإرسال عبر API إذا متاح
    if service.api_token:
        api_result = service.send_via_api(result, message)
        if api_result['success']:
            return {'success': True, 'method': 'api'}

    # استخدام رابط wa.me كبديل
    wa_link = service.generate_wa_link(result, message)
    return {'success': True, 'method': 'wa.me', 'link': wa_link}


def send_statement_whatsapp(party, invoices, phone: str, party_type: str = "customer") -> Dict[str, Any]:
    """
    دالة مساعدة لإرسال كشف حساب عبر واتساب
    """
    service = WhatsAppService()

    is_valid, result = service.validate_phone_for_whatsapp(phone)
    if not is_valid:
        return {'success': False, 'error': result}

    message = service.format_statement_message(party, invoices, party_type)

    if service.api_token:
        api_result = service.send_via_api(result, message)
        if api_result['success']:
            return {'success': True, 'method': 'api'}

    wa_link = service.generate_wa_link(result, message)
    return {'success': True, 'method': 'wa.me', 'link': wa_link}