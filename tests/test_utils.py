import pytest
from decimal import Decimal
from common.decimal_utils import (
    to_decimal, safe_add, safe_sub, safe_mul, safe_div,
    calculate_vat, calculate_withholding, money_format, financial_format,
    percentage, quantize_vat,
)


class TestDecimalUtils:
    def test_to_decimal(self):
        assert to_decimal('10.5') == Decimal('10.5')
        assert to_decimal(10) == Decimal('10')
        assert to_decimal(0) == Decimal('0')

    def test_safe_add(self):
        assert safe_add(Decimal('10'), Decimal('20')) == Decimal('30')
        assert safe_add(Decimal('10')) == Decimal('10')

    def test_safe_sub(self):
        assert safe_sub(Decimal('20'), Decimal('10')) == Decimal('10')

    def test_safe_mul(self):
        assert safe_mul(Decimal('5'), Decimal('4')) == Decimal('20')
        assert safe_mul(Decimal('5'), None) == Decimal('0')

    def test_safe_div(self):
        assert safe_div(Decimal('10'), Decimal('2')) == Decimal('5')
        assert safe_div(Decimal('10'), Decimal('0')) == Decimal('0')

    def test_percentage(self):
        assert percentage(Decimal('25'), Decimal('100')) == Decimal('25.00')
        assert percentage(Decimal('0'), Decimal('100')) == Decimal('0.00')

    def test_quantize_vat(self):
        qv = quantize_vat(Decimal('14.567'))
        assert qv >= Decimal('14.56')

    def test_calculate_vat(self):
        result = calculate_vat(Decimal('100'))
        assert result >= Decimal('13.99')
        assert result <= Decimal('14.01')

    def test_calculate_vat_custom_rate(self):
        result = calculate_vat(Decimal('100'), Decimal('0.05'))
        assert result >= Decimal('4.99')
        assert result <= Decimal('5.01')

    def test_calculate_withholding(self):
        result = calculate_withholding(Decimal('1000'), Decimal('10'))
        assert result == Decimal('100.00')
        result = calculate_withholding(Decimal('1000'), Decimal('0'))
        assert result == Decimal('0.00')

    def test_money_format(self):
        assert '1,000' in money_format(Decimal('1000'))
        assert '0' in money_format(Decimal('0'))

    def test_financial_format(self):
        result = financial_format(Decimal('1000'))
        assert '1,000' in result


class TestExceptions:
    def test_accounting_error(self):
        from common.exceptions import AccountingError
        exc = AccountingError('test error')
        assert str(exc) == 'test error'
        assert exc.code == 'ACCOUNTING_ERROR'

    def test_unbalanced_entry_error(self):
        from common.exceptions import UnbalancedEntryError
        exc = UnbalancedEntryError('unbalanced')
        assert exc.code == 'UNBALANCED_ENTRY'

    def test_insufficient_stock_error(self):
        from common.exceptions import InsufficientStockError
        exc = InsufficientStockError('no stock', 10, 5)
        assert exc.code == 'INSUFFICIENT_STOCK'
        assert exc.available == 10
        assert exc.requested == 5

    def test_entry_already_posted(self):
        from common.exceptions import EntryAlreadyPostedError
        exc = EntryAlreadyPostedError('already posted')
        assert exc.code == 'ENTRY_ALREADY_POSTED'

    def test_fiscal_year_closed(self):
        from common.exceptions import FiscalYearClosedError
        exc = FiscalYearClosedError('closed')
        assert exc.code == 'FISCAL_YEAR_CLOSED'


class TestContextProcessors:
    def test_user_permissions_context(self, rf):
        from common.context_processors import user_permissions_context
        req = rf.get('/')
        req.user = type('User', (), {'is_authenticated': False, 'is_superuser': False})()
        result = user_permissions_context(req)
        assert isinstance(result, dict)
        assert 'user_perms' in result
