import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError

from common.validators import (
    validate_positive_decimal,
    validate_non_negative_decimal,
    validate_vat_rate,
    validate_payment_method,
    validate_supplier_type,
    validate_customer_type,
    validate_entry_type,
    validate_balanced_entry,
)


class TestValidators:
    def test_validate_positive_decimal(self):
        validate_positive_decimal(10)
        validate_positive_decimal(0.01)
        with pytest.raises(ValidationError):
            validate_positive_decimal(-1)
        with pytest.raises(ValidationError):
            validate_positive_decimal(0)

    def test_validate_non_negative_decimal(self):
        validate_non_negative_decimal(0)
        validate_non_negative_decimal(10)
        with pytest.raises(ValidationError):
            validate_non_negative_decimal(-1)

    def test_validate_vat_rate(self):
        validate_vat_rate(14)
        validate_vat_rate(0)
        with pytest.raises(ValidationError):
            validate_vat_rate(-1)
        with pytest.raises(ValidationError):
            validate_vat_rate(101)

    def test_validate_payment_method(self):
        for val in ('cash', 'credit', 'check', 'transfer'):
            validate_payment_method(val)
        with pytest.raises(ValidationError):
            validate_payment_method('invalid_method')

    def test_validate_supplier_type(self):
        for val in ('company', 'individual'):
            validate_supplier_type(val)
        with pytest.raises(ValidationError):
            validate_supplier_type('local')

    def test_validate_customer_type(self):
        for val in ('company', 'individual', 'government'):
            validate_customer_type(val)
        with pytest.raises(ValidationError):
            validate_customer_type('local')

    def test_validate_entry_type(self):
        for val in ('general', 'purchase', 'sale', 'receipt', 'payment', 'depreciation', 'payroll', 'adjustment'):
            validate_entry_type(val)
        with pytest.raises(ValidationError):
            validate_entry_type('debit')

    def test_validate_balanced_entry(self):
        validate_balanced_entry(Decimal('100'), Decimal('100'))
        with pytest.raises(ValidationError):
            validate_balanced_entry(Decimal('100'), Decimal('50'))
