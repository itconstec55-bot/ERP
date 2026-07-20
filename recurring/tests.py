import pytest
from decimal import Decimal
from datetime import date
from recurring.models import RecurringJournal, RecurringJournalLine, RecurringJournalLog
from accounts.models import Account, AccountType
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestRecurringJournal:
    def test_create_recurring_journal(self):
        user = User.objects.create_user('test', 'test@test.com', 'test123')
        rj = RecurringJournal.objects.create(
            name='قيد الإيجار الشهري',
            frequency='monthly',
            next_due_date=date(2026, 8, 1),
            created_by=user,
        )
        assert rj.pk is not None
        assert 'شهري' in rj.get_frequency_display()

    def test_default_status(self):
        rj = RecurringJournal.objects.create(
            name='قيد اختبار',
            frequency='weekly',
            next_due_date=date(2026, 7, 20),
        )
        assert rj.status == 'active'

    def test_default_totals(self):
        rj = RecurringJournal.objects.create(
            name='قيد اختبار',
            frequency='daily',
            next_due_date=date(2026, 7, 20),
        )
        assert rj.total_debit == Decimal('0')
        assert rj.total_credit == Decimal('0')


@pytest.mark.django_db
class TestRecurringJournalLine:
    def test_create_line(self):
        atype = AccountType.objects.first()
        account = Account.objects.create(
            code='1000', name='النقدية',
            account_type=atype,
        )
        rj = RecurringJournal.objects.create(
            name='قيد اختبار',
            frequency='monthly',
            next_due_date=date(2026, 8, 1),
        )
        line = RecurringJournalLine.objects.create(
            journal=rj,
            account=account,
            debit=Decimal('1000'),
            credit=Decimal('0'),
        )
        assert line.pk is not None
