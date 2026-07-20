from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth.models import User
from django.test import Client
from treasury.models import Bank, BankTransaction
from .models import BankStatementItem


class BankReconciliationImportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='testuser', password='testpass123')
        self.client = Client()
        self.client.force_login(self.user)
        self.bank = Bank.objects.create(name='بنك الاختبار', account_number='ACC-001')

    def _upload_csv(self, content):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post('/bank-reconciliation/import-csv/', {
            'bank_account': str(self.bank.pk),
            'csv_file': SimpleUploadedFile(
                'stmt.csv', content.encode('utf-8-sig'),
                content_type='text/csv',
            ),
        })

    def test_import_csv_creates_items_with_decimal_amounts(self):
        csv_content = (
            "date,description,reference,debit,credit\n"
            "2026-01-05,إيداع نقدي,REF1,0,1500.50\n"
            "2026-01-06,سحب آلي,REF2,200,0\n"
        )
        resp = self._upload_csv(csv_content)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BankStatementItem.objects.count(), 2)
        item = BankStatementItem.objects.get(reference='REF1')
        self.assertEqual(item.credit_amount, Decimal('1500.50'))
        self.assertEqual(item.debit_amount, Decimal('0'))

    def test_import_csv_skips_negative_amounts(self):
        csv_content = (
            "date,description,reference,debit,credit\n"
            "2026-01-07,قيمة سالبة,REF3,-50,0\n"
        )
        resp = self._upload_csv(csv_content)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BankStatementItem.objects.count(), 0)


class BankItemMatchTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='testuser', password='testpass123')
        self.client = Client()
        self.client.force_login(self.user)
        self.bank = Bank.objects.create(name='بنك التطابق', account_number='ACC-002')
        self.other_bank = Bank.objects.create(name='بنك آخر', account_number='ACC-003')
        self.item = BankStatementItem.objects.create(
            bank_account=self.bank, transaction_date=date(2026, 1, 10),
            description='بند', debit_amount=Decimal('0'), credit_amount=Decimal('500'),
        )
        self.tx_same = BankTransaction.objects.create(
            bank=self.bank, transaction_type='deposit', date=date(2026, 1, 10),
            amount=Decimal('500'), description='معاملة',
        )
        self.tx_other = BankTransaction.objects.create(
            bank=self.other_bank, transaction_type='deposit', date=date(2026, 1, 10),
            amount=Decimal('500'), description='معاملة أخرى',
        )

    def test_match_same_bank_succeeds(self):
        resp = self.client.post(f'/bank-reconciliation/items/{self.item.pk}/match/', {
            'transaction_id': str(self.tx_same.pk),
        })
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'matched')
        self.assertEqual(self.item.matched_transaction_id, self.tx_same.pk)

    def test_match_different_bank_rejected(self):
        resp = self.client.post(f'/bank-reconciliation/items/{self.item.pk}/match/', {
            'transaction_id': str(self.tx_other.pk),
        })
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'unmatched')
        self.assertIsNone(self.item.matched_transaction_id)
