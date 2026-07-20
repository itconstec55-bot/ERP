import pytest
from decimal import Decimal
from datetime import date
from contractors.models import Contractor, Contract, InterimCertificate, ContractorPayment
from accounts.models import Account, AccountType


@pytest.mark.django_db
class TestContractor:
    def test_create(self):
        c = Contractor.objects.create(
            code='CON-001',
            name='مقاول البناء الحديث',
            contractor_type='company',
            phone='0555555555',
        )
        assert c.pk is not None
        assert 'مقاول' in str(c)

    def test_defaults(self):
        c = Contractor.objects.create(
            code='CON-002', name='مقاول 2',
            contractor_type='individual', phone='0555555555',
        )
        assert c.status == 'active'
        assert c.is_active is True


@pytest.mark.django_db
class TestContract:
    def test_create(self):
        c = Contractor.objects.create(
            code='CON-003', name='مقاول 3',
            contractor_type='company', phone='0555555555',
        )
        contract = Contract.objects.create(
            contract_number='CTR-001',
            title='مشروع بناء مبنى إداري',
            contractor=c,
            contract_amount=Decimal('500000'),
        )
        assert contract.pk is not None
        assert contract.status == 'draft'
        assert contract.vat_amount == Decimal('70000')

    def test_str(self):
        c = Contractor.objects.create(
            code='CON-004', name='مقاول 4',
            contractor_type='company', phone='0555555555',
        )
        contract = Contract.objects.create(
            contract_number='CTR-002',
            title='مشروع صيانة',
            contractor=c,
        )
        assert 'CTR-002' in str(contract)


@pytest.mark.django_db
class TestContractorPayment:
    def test_create(self):
        c = Contractor.objects.create(
            code='CON-005', name='مقاول 5',
            contractor_type='company', phone='0555555555',
        )
        contract = Contract.objects.create(
            contract_number='CTR-003',
            title='مشروع تمديدات',
            contractor=c,
        )
        payment = ContractorPayment.objects.create(
            payment_number='PMT-001',
            contract=contract,
            amount=Decimal('10000'),
            payment_method='bank_transfer',
            payment_date=date(2026, 7, 20),
        )
        assert payment.pk is not None
        assert payment.status == 'draft'
