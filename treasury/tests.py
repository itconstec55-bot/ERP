import pytest
from decimal import Decimal
from treasury.models import Bank, Safe, BankTransaction, SafeTransaction
from accounts.models import Account


@pytest.mark.django_db
class TestBank:
    def test_create_bank(self):
        bank = Bank.objects.create(
            name='بنك القاهرة',
            account_number='123456',
            current_balance=Decimal('10000.00'),
        )
        assert bank.pk is not None
        assert str(bank) == 'بنك القاهرة - 123456'

    def test_bank_defaults(self):
        bank = Bank.objects.create(name='بنك الرياض', account_number='654321')
        assert bank.is_active is True
        assert bank.current_balance == Decimal('0')


@pytest.mark.django_db
class TestSafe:
    def test_create_safe(self):
        safe = Safe.objects.create(
            name='الخزينة الرئيسية',
            current_balance=Decimal('50000.00'),
        )
        assert safe.pk is not None
        assert 'الخزينة الرئيسية' in str(safe)

    def test_safe_maximum_limit_default(self):
        safe = Safe.objects.create(name='خزينة فرعية')
        assert safe.maximum_limit == Decimal('0')


@pytest.mark.django_db
class TestBankTransaction:
    def test_create_deposit(self):
        bank = Bank.objects.create(name='بنك', account_number='111')
        tx = BankTransaction.objects.create(
            bank=bank,
            transaction_type='deposit',
            amount=Decimal('5000.00'),
            description='إيداع',
        )
        assert tx.pk is not None
        assert tx.is_posted is False

    def test_transaction_type_choices(self):
        bank = Bank.objects.create(name='بنك', account_number='222')
        tx = BankTransaction.objects.create(
            bank=bank,
            transaction_type='withdrawal',
            amount=Decimal('1000.00'),
            description='سحب',
        )
        assert tx.get_transaction_type_display() == 'سحب'
