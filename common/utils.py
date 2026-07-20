"""
أدوات مساعدة مشتركة للنظام المحاسبي
"""

import logging
from datetime import date, datetime

from django.contrib import messages
from django.http import HttpRequest

logger = logging.getLogger('accounting')

DATE_FORMAT = '%Y-%m-%d'


def parse_date(date_string: str) -> date | None:
    """
    تحليل نص تاريخ بأمان. تعيد None بدلاً من رمي استثناء عند فشل التحليل.
    """
    if not date_string or not isinstance(date_string, str):
        return None
    try:
        return datetime.strptime(date_string.strip(), DATE_FORMAT).date()
    except (ValueError, TypeError):
        return None


def parse_date_range(
    request: HttpRequest,
    param_from: str = 'date_from',
    param_to: str = 'date_to',
    default_from: date | None = None,
    default_to: date | None = None,
) -> tuple[date | None, date | None]:
    """
    تحليل نطاق تواريخ من query string مع التحقق من صيغة التاريخ ونطاق السيرفر.

    تعيد tuple من (date_from, date_to). إذا كان التاريخ في صيغة خاطئة، تُضيف رسالة خطأ
    وتعيد (None, None). إذا كان date_from > date_to، تُضيف رسالة تحذير وتُبادلهم.

    Args:
        request: كائن الطلب
        param_from: اسم معامل تاريخ البداية
        param_to: اسم معامل تاريخ النهاية
        default_from: تاريخ افتراضي للبداية إذا لم يُحدد
        default_to: تاريخ افتراضي للنهاية إذا لم يُحدد

    Returns:
        tuple: (date_from, date_to) كـ date objects أو None
    """
    raw_from = request.GET.get(param_from)
    raw_to = request.GET.get(param_to)

    date_from = parse_date(raw_from) if raw_from else None
    date_to = parse_date(raw_to) if raw_to else None

    if raw_from and date_from is None:
        messages.warning(request, f'صيغة تاريخ البداية غير صحيحة: "{raw_from}". الصيغة المطلوبة: YYYY-MM-DD')
        return None, None
    if raw_to and date_to is None:
        messages.warning(request, f'صيغة تاريخ النهاية غير صحيحة: "{raw_to}". الصيغة المطلوبة: YYYY-MM-DD')
        return None, None

    if date_from is None and default_from is not None:
        date_from = default_from
    if date_to is None and default_to is not None:
        date_to = default_to

    if date_from and date_to and date_from > date_to:
        messages.warning(request, 'تاريخ البداية أحدث من تاريخ النهاية - تم تبادلهما تلقائياً')
        date_from, date_to = date_to, date_from

    return date_from, date_to


# Safe user-facing error messages — never expose internal details
SAFE_ERROR_MESSAGES = {
    'import': 'حدث خطأ أثناء الاستيراد. تأكد من صحة بيانات الملف وحاول مرة أخرى.',
    'post': 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.',
    'backup_create': 'فشل إنشاء النسخة الاحتياطية.',
    'backup_restore': 'فشل استرجاع النسخة الاحتياطية.',
    'backup_export': 'فشل تصدير البيانات.',
    'backup_import': 'فشل استيراد البيانات.',
    'sync': 'فشلت المزامنة. تأكد من الاتصال بالخادم وحاول مرة أخرى.',
    'connection': 'فشل الاتصال بالخادم.',
    'email': 'فشل إرسال البريد الإلكتروني.',
    'generic': 'حدث خطأ غير متوقع. يرجى المحاولة لاحقاً.',
}
