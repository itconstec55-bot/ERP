"""
أدوات دقة العشرية للعمليات المالية
تدعم العمليات الحسابية بدقة 10 أرقام عشرية للعرض والتخزين
"""
from decimal import Decimal, ROUND_HALF_UP, localcontext, getcontext
from typing import Union, List, Tuple, Dict, Any
from functools import wraps

# إعداد السياق العام للدقة العالية
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

# الثوابت
QUANTIZE_10 = Decimal('0.0000000001')  # 10 أرقام عشرية للتخزين
QUANTIZE_DISPLAY = Decimal('0.01')      # رقمين عشريين للعرض
VAT_RATE = Decimal('0.14')              # 14% ضريبة
HUNDRED = Decimal('100')

Number = Union[int, float, str, Decimal]


def to_decimal(value: Number) -> Decimal:
    """تحويل آمن إلى Decimal"""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def quantize_10(value: Number) -> Decimal:
    """تقريب إلى 10 أرقام عشرية (للتخزين والحسابات الداخلية)"""
    if value is None:
        return Decimal('0')
    d = to_decimal(value)
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        return d.quantize(QUANTIZE_10)


def quantize_display(value: Number) -> Decimal:
    """تقريب لرقمين عشريين (للعرض والتقارير)"""
    if value is None:
        return Decimal('0.00')
    d = to_decimal(value)
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        return d.quantize(QUANTIZE_DISPLAY)


def safe_add(*values: Number) -> Decimal:
    """جمع آمن مع تقريب"""
    result = Decimal('0')
    for v in values:
        result += to_decimal(v)
    return quantize_10(result)


def safe_sub(value1: Number, value2: Number) -> Decimal:
    """طرح آمن مع تقريب"""
    return quantize_10(to_decimal(value1) - to_decimal(value2))


def safe_mul(value1: Number, value2: Number) -> Decimal:
    """ضرب آمن مع تقريب"""
    return quantize_10(to_decimal(value1) * to_decimal(value2))


def safe_div(value1: Number, value2: Number) -> Decimal:
    """قسمة آمنة مع تقريب (ترجع 0 إذا القاسم صفر)"""
    divisor = to_decimal(value2)
    if divisor == 0:
        return Decimal('0')
    return quantize_10(to_decimal(value1) / divisor)


def percentage(numerator: Number, denominator: Number) -> Decimal:
    """حساب النسبة المئوية بأمان"""
    return quantize_10(safe_div(numerator, denominator) * HUNDRED)


def quantize_vat(value: Number) -> Decimal:
    """تقريب مخصص للضريبة (10 أرقام)"""
    return quantize_10(value)


def calculate_vat(amount: Number, rate: Number = VAT_RATE) -> Decimal:
    """حساب الضريبة مع تقريب"""
    return quantize_vat(to_decimal(amount) * to_decimal(rate))


def calculate_withholding(amount: Number, rate_percent: Number) -> Decimal:
    """حساب الخصم والتحصيل"""
    rate = safe_div(rate_percent, HUNDRED)
    return quantize_vat(to_decimal(amount) * rate)


# ==================== فئة FinancialDecimal للعمليات المتسلسلة ====================

class FinancialDecimal:
    """
    غلاف لـ Decimal يدعم العمليات المتسلسلة مع تقريب تلقائي
    """
    __slots__ = ('_value',)
    
    def __init__(self, value: Number = 0):
        self._value = quantize_10(value)
    
    @property
    def raw(self) -> Decimal:
        return self._value
    
    def __add__(self, other: Number) -> 'FinancialDecimal':
        return FinancialDecimal(quantize_10(self._value + to_decimal(other)))
    
    def __sub__(self, other: Number) -> 'FinancialDecimal':
        return FinancialDecimal(quantize_10(self._value - to_decimal(other)))
    
    def __mul__(self, other: Number) -> 'FinancialDecimal':
        return FinancialDecimal(quantize_10(self._value * to_decimal(other)))
    
    def __truediv__(self, other: Number) -> 'FinancialDecimal':
        return FinancialDecimal(safe_div(self._value, other))
    
    def __radd__(self, other: Number) -> 'FinancialDecimal':
        return self.__add__(other)
    
    def __rsub__(self, other: Number) -> 'FinancialDecimal':
        return FinancialDecimal(quantize_10(to_decimal(other) - self._value))
    
    def __rmul__(self, other: Number) -> 'FinancialDecimal':
        return self.__mul__(other)
    
    def __rtruediv__(self, other: Number) -> 'FinancialDecimal':
        return FinancialDecimal(safe_div(other, self._value))
    
    def __lt__(self, other: Number) -> bool:
        return self._value < to_decimal(other)
    
    def __le__(self, other: Number) -> bool:
        return self._value <= to_decimal(other)
    
    def __gt__(self, other: Number) -> bool:
        return self._value > to_decimal(other)
    
    def __ge__(self, other: Number) -> bool:
        return self._value >= to_decimal(other)
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, FinancialDecimal):
            return self._value == other._value
        return self._value == to_decimal(other) if isinstance(other, (int, float, str, Decimal)) else False
    
    def __hash__(self) -> int:
        return hash(self._value)
    
    def __neg__(self) -> 'FinancialDecimal':
        return FinancialDecimal(-self._value)
    
    def abs(self) -> 'FinancialDecimal':
        return FinancialDecimal(abs(self._value))
    
    def quantize_10(self) -> 'FinancialDecimal':
        self._value = quantize_10(self._value)
        return self
    
    def quantize_display(self) -> 'FinancialDecimal':
        return FinancialDecimal(quantize_display(self._value))
    
    def to_display(self) -> Decimal:
        return quantize_display(self._value)
    
    def __repr__(self) -> str:
        return f"FinancialDecimal({self._value})"
    
    def __str__(self) -> str:
        return str(self._value)
    
    def __float__(self) -> float:
        return float(self._value)
    
    def __int__(self) -> int:
        return int(self._value)


# ==================== المزخرفات للعمليات الآمنة ====================

def safe_arithmetic(func):
    """مُزخرف للعمليات الحسابية مع تقريب تلقائي"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with localcontext() as ctx:
            ctx.prec = 28
            ctx.rounding = ROUND_HALF_UP
            result = func(*args, **kwargs)
            if isinstance(result, Decimal):
                return quantize_10(result)
            elif isinstance(result, (list, tuple)):
                return type(result)(quantize_10(v) if isinstance(v, Decimal) else v for v in result)
            elif isinstance(result, dict):
                return {k: quantize_10(v) if isinstance(v, Decimal) else v for k, v in result.items()}
            return result
    return wrapper


@safe_arithmetic
def calculate_invoice_totals(
    lines: List[Dict[str, Any]],
    discount_amount: Number = 0,
    withholding_rate: Number = 0,
    is_tax_invoice: bool = True
) -> Dict[str, Decimal]:
    """
    حساب إجماليات الفاتورة مع دقة مالية
    
    Args:
        lines: قائمة البنود [{'quantity', 'unit_price', 'discount_percent', 'cost_price'}]
        discount_amount: خصم على الفاتورة
        withholding_rate: معدل الخصم والتحصيل (1, 3, 5...)
        is_tax_invoice: هل فاتورة ضريبية
    
    Returns:
        قاموس بالإجماليات
    """
    subtotal = Decimal('0')
    cost_total = Decimal('0')
    
    for line in lines:
        qty = to_decimal(line.get('quantity', 0))
        price = to_decimal(line.get('unit_price', 0))
        cost = to_decimal(line.get('cost_price', 0))
        disc_pct = to_decimal(line.get('discount_percent', 0))
        
        line_total = safe_mul(qty, price)
        if disc_pct > 0:
            line_total -= safe_mul(line_total, safe_div(line.get('discount_percent', 0), HUNDRED))
        
        subtotal += line_total
        cost_total += safe_mul(qty, cost)
    
    discount_amount = to_decimal(discount_amount)
    
    # ضريبة القيمة المضافة
    vat_amount = Decimal('0')
    if is_tax_invoice:
        vat_amount = calculate_vat(subtotal)
    
    # الخصم والتحصيل
    withholding_rate = to_decimal(withholding_rate)
    withholding_amount = Decimal('0')
    if withholding_rate > 0:
        rate = safe_div(withholding_rate, HUNDRED)
        withholding_amount = quantize_vat(subtotal * rate)
    
    discount_amount = to_decimal(discount_amount)
    total = safe_add(subtotal, vat_amount, withholding_amount)
    total = safe_sub(total, discount_amount)
    
    return {
        'subtotal': quantize_10(subtotal),
        'vat_amount': quantize_10(vat_amount),
        'discount_amount': quantize_10(discount_amount),
        'withholding_amount': quantize_10(withholding_amount),
        'total_amount': quantize_10(total),
        'cost_of_goods': quantize_10(cost_total),
        'gross_profit': quantize_10(to_decimal(0) + sum(
            to_decimal(line.get('total_price', 0)) - 
            safe_mul(to_decimal(line.get('quantity', 0)), to_decimal(line.get('cost_price', 0)))
            for line in lines
        )),
    }


def validate_invoice_precision(invoice) -> List[str]:
    """
    التحقق من دقة الفاتورة وإرجاع قائمة بالأخطاء
    """
    errors = []
    
    # التحقق من أن الإجماليات متسقة
    calculated = calculate_invoice_totals([
        {
            'quantity': line.quantity,
            'unit_price': line.unit_price,
            'discount_percent': line.discount_percent,
            'cost_price': getattr(line, 'cost_price', 0),
        }
        for line in invoice.lines.all()
    ], 
        discount_amount=invoice.discount_amount,
        withholding_rate=invoice.withholding_tax_type,
        is_tax_invoice=invoice.is_tax_invoice
    )
    
    # مقارنة الإجماليات
    if invoice.subtotal != calculated['subtotal']:
        errors.append(f"المجموع الفرعي غير متطابق: المخزن={invoice.subtotal}, المحسوب={calculated['subtotal']}")
    
    if invoice.vat_amount != calculated['vat_amount']:
        errors.append(f"الضريبة غير متطابقة: المخزن={invoice.vat_amount}, المحسوب={calculated['vat_amount']}")
    
    if invoice.total_amount != calculated['total_amount']:
        errors.append(f"الإجمالي غير متطابق: المخزن={invoice.total_amount}, المحسوب={calculated['total_amount']}")
    
    if invoice.withholding_tax_amount != calculated['withholding_amount']:
        errors.append(f"الخصم والتحصيل غير متطابق: المخزن={invoice.withholding_tax_amount}, المحسوب={calculated['withholding_amount']}")
    
    return errors


# ==================== دوال مساعدة للقوالب ====================

def financial_format(value: Number) -> str:
    """تنسيق الرقم للعرض المالي (فاصل آلاف + رقمان عشريان)"""
    if value is None:
        return "0.00"
    d = quantize_display(value)
    # إضافة فاصل الآلاف
    parts = f"{d:,.2f}".split('.')
    return f"{parts[0]}.{parts[1]}"


def financial_decimal(value: Number) -> Decimal:
    """فلتر قوالب: تحويل إلى Decimal للعرض المالي"""
    return quantize_display(value)


def money_format(value: Number, currency: str = "ج.م") -> str:
    """تنسيق كامل للعملة مع الرمز"""
    return f"{financial_format(value)} {currency}"