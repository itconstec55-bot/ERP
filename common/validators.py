"""
Validators للبيانات المالية والمحاسبية
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


def validate_positive_decimal(value):
    """
    التحقق من أن القيمة العشرية موجبة (أكبر من صفر)
    """
    if value is not None and value <= Decimal('0'):
        raise ValidationError(_('القيمة يجب أن تكون أكبر من صفر'), params={'value': value})


def validate_non_negative_decimal(value):
    """
    التحقق من أن القيمة العشرية غير سالبة
    """
    if value is not None and value < Decimal('0'):
        raise ValidationError(_('القيمة لا يمكن أن تكون سالبة'), params={'value': value})


def validate_balanced_entry(debit, credit):
    """
    التحقق من توازن القيد (المدين = الدائن)
    """
    if debit != credit:
        raise ValidationError(
            _('القيد غير متوازن: مدين=%(debit)s، دائن=%(credit)s'), params={'debit': debit, 'credit': credit}
        )


def validate_account_codes_exist(codes):
    """
    التحقق من وجود رموز الحسابات في قاعدة البيانات
    """
    from accounts.models import Account

    if not codes:
        return

    existing = set(Account.objects.filter(code__in=codes).values_list('code', flat=True))
    missing = set(codes) - existing
    if missing:
        raise ValidationError(_('حسابات غير موجودة: %(missing)s'), params={'missing': ', '.join(missing)})


def validate_vat_rate(value):
    """
    التحقق من نسبة الضريبة (0-100)
    """
    if value is not None and (value < Decimal('0') or value > Decimal('100')):
        raise ValidationError(_('نسبة الضريبة يجب أن تكون بين 0 و 100'), params={'value': value})


def validate_withholding_tax_type(value):
    """
    التحقق من نوع الخصم والتحصيل (0, 1, 3, 5)
    """
    valid_types = [0, 1, 3, 5]
    if value not in valid_types:
        raise ValidationError(
            _('نوع الخصم والتحصيل غير صالح. القيم المسموحة: %(valid)s'),
            params={'valid': ', '.join(str(v) for v in valid_types)},
        )


def validate_payment_method(value):
    """
    التحقق من طريقة الدفع
    """
    valid_methods = ['cash', 'credit', 'check', 'transfer']
    if value not in valid_methods:
        raise ValidationError(
            _('طريقة دفع غير صالحة. القيم المسموحة: %(valid)s'), params={'valid': ', '.join(valid_methods)}
        )


def validate_supplier_type(value):
    """
    التحقق من نوع المورد
    """
    valid_types = ['company', 'individual']
    if value not in valid_types:
        raise ValidationError(
            _('نوع المورد غير صالح. القيم المسموحة: %(valid)s'), params={'valid': ', '.join(valid_types)}
        )


def validate_customer_type(value):
    """
    التحقق من نوع العميل
    """
    valid_types = ['company', 'individual', 'government']
    if value not in valid_types:
        raise ValidationError(
            _('نوع العميل غير صالح. القيم المسموحة: %(valid)s'), params={'valid': ', '.join(valid_types)}
        )


def validate_entry_type(value):
    """
    التحقق من نوع القيد المحاسبي
    """
    valid_types = ['general', 'purchase', 'sale', 'receipt', 'payment', 'depreciation', 'payroll', 'adjustment']
    if value not in valid_types:
        raise ValidationError(
            _('نوع القيد غير صالح. القيم المسموحة: %(valid)s'), params={'valid': ', '.join(valid_types)}
        )


class FinancialValidator:
    """
    فئة موحدة للتحقق من البيانات المالية
    """

    @staticmethod
    def validate_invoice_totals(subtotal, vat_amount, discount_amount, withholding_tax_amount, total_amount):
        """
        التحقق من صحة إجماليات الفاتورة
        """
        from common.decimal_utils import safe_add, safe_sub

        expected_total = safe_add(subtotal, vat_amount)
        expected_total = safe_sub(expected_total, discount_amount)
        if withholding_tax_amount:
            expected_total = safe_sub(expected_total, withholding_tax_amount)

        if total_amount != expected_total:
            raise ValidationError(f'الإجمالي غير صحيح. المتوقع: {expected_total}, المدخل: {total_amount}')

    @staticmethod
    def validate_journal_entry_lines(lines):
        """
        التحقق من بنود القيد المحاسبي
        """
        if not lines:
            raise ValidationError('القيد يجب أن يحتوي على بندين على الأقل')

        total_debit = sum(Decimal(str(l.get('debit', 0))) for l in lines)
        total_credit = sum(Decimal(str(l.get('credit', 0))) for l in lines)

        validate_balanced_entry(total_debit, total_credit)

        # التحقق من عدم وجود سطر به مدين ودائن معاً
        for line in lines:
            debit = Decimal(str(line.get('debit', 0)))
            credit = Decimal(str(line.get('credit', 0)))
            if debit > 0 and credit > 0:
                raise ValidationError('لا يمكن أن يكون السطر مديناً ودائناً في نفس الوقت')

    @staticmethod
    def validate_invoice_payment(payment_amount, remaining_amount):
        """
        التحقق من مبلغ الدفع مقابل المبلغ المتبقي
        """
        if payment_amount > remaining_amount:
            raise ValidationError(f'مبلغ الدفع ({payment_amount}) أكبر من المبلغ المتبقي ({remaining_amount})')

    @staticmethod
    def validate_stock_availability(product, requested_quantity, warehouse=None):
        """
        التحقق من توفر المخزون
        """
        from warehouses.models import WarehouseProduct

        if warehouse:
            available = (
                WarehouseProduct.objects.filter(product=product, warehouse=warehouse).aggregate(
                    total=models.Sum('quantity')
                )['total']
                or 0
            )
        else:
            available = (
                WarehouseProduct.objects.filter(product=product).aggregate(total=models.Sum('quantity'))['total'] or 0
            )

        if available < requested_quantity:
            raise ValidationError(f'مخزون غير كافٍ. المتوفر: {available}, المطلوب: {requested_quantity}')
