import pytest
from decimal import Decimal


@pytest.mark.django_db
class TestTreasuryModels:
    def test_bank_creation(self):
        from treasury.models import Bank
        bank = Bank.objects.create(name='بنك مصر', account_number='12345', current_balance=Decimal('10000'))
        assert bank.pk is not None
        assert 'بنك مصر' in str(bank)
        assert bank.is_active is True

    def test_bank_deactivation(self):
        from treasury.models import Bank
        bank = Bank.objects.create(name='بنك القاهرة', account_number='67890')
        bank.is_active = False
        bank.save()
        assert bank.is_active is False

    def test_safe_creation(self):
        from treasury.models import Safe
        safe = Safe.objects.create(name='الخزينة الرئيسية', current_balance=Decimal('5000'))
        assert safe.pk is not None
        assert 'الخزينة' in str(safe)

    def test_bank_transaction_creation(self):
        from treasury.models import Bank, BankTransaction
        bank = Bank.objects.create(name='بنك test', account_number='11111')
        tx = BankTransaction.objects.create(
            bank=bank, amount=Decimal('1000'), transaction_type='deposit', description='إيداع'
        )
        assert tx.pk is not None

    def test_safe_transaction_creation(self):
        from treasury.models import Safe, SafeTransaction
        safe = Safe.objects.create(name='خزينة test')
        tx = SafeTransaction.objects.create(
            safe=safe, amount=Decimal('500'), transaction_type='deposit'
        )
        assert tx.pk is not None


@pytest.mark.django_db
class TestCompanyModels:
    def test_company_creation(self):
        from company.models import Company
        c = Company.objects.create(name='شركة اختبار')
        assert c.pk is not None

    def test_company_branch_creation(self):
        from company.models import Company, CompanyBranch
        comp = Company.objects.create(name='الشركة الأم')
        branch = CompanyBranch.objects.create(company=comp, name='فرع رئيسي')
        assert branch.pk is not None

    def test_company_str(self):
        from company.models import Company
        c = Company.objects.create(name='شركة التحدي')
        assert 'التحدي' in str(c)


@pytest.mark.django_db
class TestNotificationsModels:
    def test_notification_template_creation(self):
        from notifications.models import NotificationTemplate
        nt = NotificationTemplate.objects.create(
            name='test template',
            event='invoice_created',
            subject_template='فاتورة جديدة',
            body_template='تم إنشاء فاتورة جديدة',
        )
        assert nt.pk is not None

    def test_notification_log_creation(self):
        from notifications.models import NotificationTemplate, NotificationLog
        nt = NotificationTemplate.objects.create(
            name='test',
            event='invoice_created',
            subject_template='test',
            body_template='test body',
        )
        log = NotificationLog.objects.create(
            template=nt, recipient_email='test@test.com', subject='test', body='test body', success=True
        )
        assert log.pk is not None


@pytest.mark.django_db
class TestCommonModels:
    def test_sequence_number_creation(self):
        from common.models import SequenceNumber
        sn = SequenceNumber.objects.create(sequence_type='sales_invoice', prefix='INV')
        assert sn.pk is not None
        assert sn.last_number == 0

    def test_sequence_number_increment(self):
        from common.models import SequenceNumber
        sn = SequenceNumber.objects.create(sequence_type='purchase_invoice', prefix='PINV')
        sn.last_number += 1
        sn.save()
        assert sn.last_number == 1


@pytest.mark.django_db
class TestCurrencyModels:
    def test_currency_str(self):
        from currency.models import Currency
        c = Currency.objects.create(code='USD', name='دولار أمريكي', symbol='$')
        assert 'USD' in str(c)

    def test_currency_defaults(self):
        from currency.models import Currency
        c = Currency.objects.create(code='EUR', name='يورو', symbol='€')
        assert c.is_active is True
        assert c.exchange_rate_to_egp == Decimal('1.000000')

    def test_currency_base(self):
        from currency.models import Currency
        c = Currency.objects.create(code='EGP', name='جنيه', symbol='ج.م', is_base=True)
        assert c.is_base is True
