"""
استثناءات مخصصة للنظام المحاسبي
"""
from typing import Optional
from decimal import Decimal


class AccountingError(Exception):
    """استثناء أساسي لأخطاء المحاسبة"""
    
    def __init__(self, message: str, code: str = 'ACCOUNTING_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


class UnbalancedEntryError(AccountingError):
    """القيد غير متوازن - المدين لا يساوي الدائن"""
    
    def __init__(self, message: str = 'القيد غير متوازن'):
        super().__init__(message, 'UNBALANCED_ENTRY')


class EntryAlreadyPostedError(AccountingError):
    """القيد مرحل بالفعل"""
    
    def __init__(self, message: str = 'القيد مرحل بالفعل'):
        super().__init__(message, 'ENTRY_ALREADY_POSTED')


class EntryNotPostedError(AccountingError):
    """القيد غير مرحل"""
    
    def __init__(self, message: str = 'القيد غير مرحل'):
        super().__init__(message, 'ENTRY_NOT_POSTED')


class AccountNotFoundError(AccountingError):
    """الحساب المحاسبي غير موجود"""
    
    def __init__(self, message: str = 'الحساب المحاسبي غير موجود', missing_codes: list = None):
        self.missing_codes = missing_codes or []
        super().__init__(message, 'ACCOUNT_NOT_FOUND')


class InsufficientStockError(AccountingError):
    """مخزون غير كافٍ للبيع"""
    
    def __init__(self, product_name: str, available: Decimal, requested: Decimal):
        self.product_name = product_name
        self.available = available
        self.requested = requested
        message = f'مخزون غير كافٍ للمنتج {product_name}: المتوفر {available}، المطلوب {requested}'
        super().__init__(message, 'INSUFFICIENT_STOCK')


class InvalidVoucherNumberError(AccountingError):
    """رقم سند غير صالح"""
    
    def __init__(self, message: str = 'رقم السند غير صالح'):
        super().__init__(message, 'INVALID_VOUCHER_NUMBER')


class DuplicateVoucherNumberError(AccountingError):
    """رقم سند مكرر"""
    
    def __init__(self, message: str = 'رقم السند مستخدم مسبقاً'):
        super().__init__(message, 'DUPLICATE_VOUCHER_NUMBER')


class FiscalYearClosedError(AccountingError):
    """السنة المالية مغلقة"""
    
    def __init__(self, message: str = 'السنة المالية مغلقة - لا يمكن التعديل'):
        super().__init__(message, 'FISCAL_YEAR_CLOSED')


class InvalidPeriodError(AccountingError):
    """فترة محاسبية غير صحيحة"""
    
    def __init__(self, message: str = 'الفترة المحاسبية غير صحيحة'):
        super().__init__(message, 'INVALID_PERIOD')


# ==================== استثناءات واتساب ====================

class WhatsAppError(AccountingError):
    """استثناء أساسي لأخطاء واتساب"""
    pass


class WhatsAppAuthError(WhatsAppError):
    """خطأ في مصادقة واتساب"""
    pass


class WhatsAppRateLimitError(WhatsAppError):
    """تجاوز حد الإرسال"""
    pass


class WhatsAppInvalidPhoneError(WhatsAppError):
    """رقم هاتف غير صالح"""
    pass


class WhatsAppMessageTooLongError(WhatsAppError):
    """الرسالة طويلة جداً"""
    pass


class WhatsAppNetworkError(WhatsAppError):
    """خطأ في الشبكة"""
    pass


class WhatsAppAPIError(WhatsAppError):
    """خطأ في API واتساب"""
    pass


class WhatsAppWebhookVerificationError(WhatsAppError):
    """فشل التحقق من webhook"""
    pass