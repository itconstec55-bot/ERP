from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from .models import AccountType, Account, JournalEntry, JournalEntryLine


class AccountTypeModelTest(TestCase):
    def setUp(self):
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]

    def test_account_type_creation(self):
        self.assertEqual(str(self.acc_type), 'asset - أصول')

    def test_account_type_str_representation(self):
        self.assertEqual(self.acc_type.code, 'asset')


class AccountModelTest(TestCase):
    def setUp(self):
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        self.account = Account.objects.create(
            code='1100', name='النقدية', account_type=self.acc_type,
            opening_balance=Decimal('1000.00'),
        )

    def test_account_creation(self):
        self.assertEqual(self.account.opening_balance, Decimal('1000.00'))

    def test_account_opening_balance_sets_current_balance(self):
        self.assertEqual(self.account.opening_balance, Decimal('1000.00'))

    def test_get_balance_display_asset_debit(self):
        self.assertIn('مدين', self.account.get_balance_display())

    def test_get_balance_display_liability_credit(self):
        liab_type = AccountType.objects.update_or_create(
            code='liability', defaults={'name': 'خصوم', 'account_type': 'liability'}
        )[0]
        liab = Account.objects.create(
            code='2000', name='موردون', account_type=liab_type,
            opening_balance=Decimal('500.00'),
        )
        self.assertIn('دائن', liab.get_balance_display())

    def test_parent_child_relationship(self):
        child = Account.objects.create(
            code='1110', name='نقدية بالصندوق', account_type=self.acc_type,
            parent=self.account,
        )
        self.assertEqual(child.parent, self.account)
        self.assertIn(child, self.account.children.all())


class JournalEntryModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        self.exp_type = AccountType.objects.update_or_create(
            code='expense', defaults={'name': 'مصروفات', 'account_type': 'expense'}
        )[0]
        self.rev_type = AccountType.objects.update_or_create(
            code='revenue', defaults={'name': 'إيرادات', 'account_type': 'revenue'}
        )[0]
        self.cash = Account.objects.create(
            code='1100', name='النقدية', account_type=self.acc_type,
        )
        self.expense = Account.objects.create(
            code='5100', name='مصروفات', account_type=self.exp_type,
        )
        self.revenue = Account.objects.create(
            code='4100', name='إيرادات', account_type=self.rev_type,
        )

    def _create_balanced_entry(self):
        entry = JournalEntry.objects.create(
            entry_number='JE-001', entry_type='general',
            description='قيد اختبار', created_by=self.user,
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=self.cash,
            debit=Decimal('1000.00'), credit=Decimal('0.00'),
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=self.revenue,
            debit=Decimal('0.00'), credit=Decimal('1000.00'),
        )
        entry.calculate_totals()
        return entry

    def test_journal_entry_creation(self):
        entry = self._create_balanced_entry()
        self.assertEqual(entry.total_debit, Decimal('1000.00'))
        self.assertEqual(entry.total_credit, Decimal('1000.00'))
        self.assertTrue(entry.is_balanced())

    def test_journal_entry_not_balanced_raises_error(self):
        entry = JournalEntry.objects.create(
            entry_number='JE-002', entry_type='general',
            description='قيد غير متوازن', created_by=self.user,
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=self.cash,
            debit=Decimal('1000.00'), credit=Decimal('0.00'),
        )
        entry.calculate_totals()
        with self.assertRaises(ValueError):
            entry.post()

    def test_post_updates_account_balances(self):
        entry = self._create_balanced_entry()
        self.assertEqual(self.cash.current_balance, Decimal('0.00'))
        entry.post()
        self.cash.refresh_from_db()
        self.revenue.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('1000.00'))
        self.assertEqual(self.revenue.current_balance, Decimal('-1000.00'))
        entry.refresh_from_db()
        self.assertTrue(entry.is_posted)

    def test_double_post_raises_error(self):
        entry = self._create_balanced_entry()
        entry.post()
        with self.assertRaises(ValueError):
            entry.post()

    def test_reverse_reverses_balances(self):
        entry = self._create_balanced_entry()
        entry.post()
        self.cash.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('1000.00'))
        entry.reverse()
        self.cash.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('0.00'))
        entry.refresh_from_db()
        self.assertTrue(entry.is_reversed)

    def test_reverse_unposted_raises_error(self):
        entry = self._create_balanced_entry()
        with self.assertRaises(ValueError):
            entry.reverse()

    def test_multi_line_entry(self):
        entry = JournalEntry.objects.create(
            entry_number='JE-003', entry_type='general',
            description='قيد بثلاثة أسطر', created_by=self.user,
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=self.expense,
            debit=Decimal('500.00'), credit=Decimal('0.00'),
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=self.cash,
            debit=Decimal('0.00'), credit=Decimal('500.00'),
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=self.revenue,
            debit=Decimal('200.00'), credit=Decimal('0.00'),
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=self.cash,
            debit=Decimal('0.00'), credit=Decimal('200.00'),
        )
        entry.calculate_totals()
        self.assertTrue(entry.is_balanced())
        entry.post()
        self.cash.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('-700.00'))
