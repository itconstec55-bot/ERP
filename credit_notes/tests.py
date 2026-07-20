import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from credit_notes.models import CreditNote
from accounts.models import Account, JournalEntry, JournalEntryLine
from company.models import Company


@pytest.mark.django_db
class TestCreditNote:
    def test_create_credit_note(self):
        cn = CreditNote.objects.create(
            note_type='credit_note',
            note_number='CN-001',
            total_amount=Decimal('1000.00'),
        )
        assert cn.pk is not None
        assert cn.note_number == 'CN-001'
        assert cn.total_amount == Decimal('1000.00')

    def test_credit_note_str(self):
        cn = CreditNote.objects.create(
            note_type='credit_note',
            note_number='CN-002',
            total_amount=Decimal('500.00'),
        )
        assert 'CN-002' in str(cn)
        assert 'دائن' in str(cn) or 'credit_note' in str(cn)

    def test_credit_note_default_values(self):
        cn = CreditNote.objects.create(
            note_type='debit_note',
            note_number='CN-003',
            total_amount=Decimal('0'),
        )
        assert cn.is_posted is False
        assert cn.note_type == 'debit_note'

    def test_credit_note_status_choices(self):
        cn = CreditNote.objects.create(
            note_type='credit_note',
            note_number='CN-004',
            total_amount=Decimal('100'),
        )
        assert cn.is_posted is False
        assert not hasattr(cn, 'status') or cn.status == 'draft'
