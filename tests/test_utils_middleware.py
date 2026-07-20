"""
اختبارات الأدوات المساعدة والـ Middleware والعمليات المالية الحرجة
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import JsonResponse
from django.test import RequestFactory, TestCase

from accounting_system.middleware import ErrorHandlingMiddleware, RequestLoggingMiddleware
from accounts.models import Account, AccountType
from common.accounting_service import JournalEntryService
from common.exceptions import AccountNotFoundError, UnbalancedEntryError
from common.utils import SAFE_ERROR_MESSAGES, parse_date, parse_date_range


# ============================================================
# اختبارات parse_date
# ============================================================
class ParseDateTest(TestCase):
    """اختبار تحليل التواريخ بأمان"""

    def test_valid_date(self):
        result = parse_date('2024-06-15')
        self.assertEqual(result, date(2024, 6, 15))

    def test_valid_date_with_spaces(self):
        result = parse_date('  2024-06-15  ')
        self.assertEqual(result, date(2024, 6, 15))

    def test_invalid_format_slashes(self):
        result = parse_date('15/06/2024')
        self.assertIsNone(result)

    def test_invalid_format_text(self):
        result = parse_date('not-a-date')
        self.assertIsNone(result)

    def test_empty_string(self):
        result = parse_date('')
        self.assertIsNone(result)

    def test_none(self):
        result = parse_date(None)
        self.assertIsNone(result)

    def test_non_string(self):
        result = parse_date(12345)
        self.assertIsNone(result)

    def test_partial_date(self):
        result = parse_date('2024-06')
        self.assertIsNone(result)


# ============================================================
# اختبارات parse_date_range
# ============================================================
class ParseDateRangeTest(TestCase):
    """اختبار تحليل نطاق التواريخ من query string"""

    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, **params):
        request = self.factory.get('/', params)
        request.session = 'session'
        request._messages = FallbackStorage(request)
        return request

    def test_valid_range(self):
        request = self._make_request(date_from='2024-01-01', date_to='2024-12-31')
        df, dt = parse_date_range(request)
        self.assertEqual(df, date(2024, 1, 1))
        self.assertEqual(dt, date(2024, 12, 31))

    def test_reversed_range_swapped(self):
        request = self._make_request(date_from='2024-12-31', date_to='2024-01-01')
        df, dt = parse_date_range(request)
        self.assertEqual(df, date(2024, 1, 1))
        self.assertEqual(dt, date(2024, 12, 31))

    def test_invalid_date_from_returns_none(self):
        request = self._make_request(date_from='bad-date', date_to='2024-12-31')
        df, dt = parse_date_range(request)
        self.assertIsNone(df)

    def test_invalid_date_to_returns_none(self):
        request = self._make_request(date_from='2024-01-01', date_to='bad-date')
        df, dt = parse_date_range(request)
        self.assertIsNone(dt)

    def test_defaults_applied(self):
        request = self._make_request()
        default_from = date(2024, 1, 1)
        default_to = date(2024, 6, 30)
        df, dt = parse_date_range(request, default_from=default_from, default_to=default_to)
        self.assertEqual(df, default_from)
        self.assertEqual(dt, default_to)

    def test_no_params_no_defaults(self):
        request = self._make_request()
        df, dt = parse_date_range(request)
        self.assertIsNone(df)
        self.assertIsNone(dt)


# ============================================================
# اختبارات ErrorHandlingMiddleware
# ============================================================
class ErrorHandlingMiddlewareTest(TestCase):
    """اختبار middleware معالجة الأخطاء"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ErrorHandlingMiddleware(lambda r: None)

    def _make_request(self, accept_json=False):
        request = self.factory.get('/test/')
        if accept_json:
            request.META['HTTP_ACCEPT'] = 'application/json'
        user = MagicMock()
        user.is_authenticated = True
        user.pk = 1
        request.user = user
        request.session = 'session'
        request._messages = FallbackStorage(request)
        return request

    def test_accounting_error_json_response(self):
        request = self._make_request(accept_json=True)
        exc = UnbalancedEntryError('القيد غير متوازن')
        response = self.middleware.process_exception(request, exc)
        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 400)

    def test_accounting_error_non_json_returns_none(self):
        request = self._make_request(accept_json=False)
        exc = UnbalancedEntryError('test')
        response = self.middleware.process_exception(request, exc)
        self.assertIsNone(response)

    def test_permission_error_json(self):
        request = self._make_request(accept_json=True)
        exc = PermissionError('denied')
        response = self.middleware.process_exception(request, exc)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)

    def test_file_not_found_json(self):
        request = self._make_request(accept_json=True)
        exc = FileNotFoundError('missing')
        response = self.middleware.process_exception(request, exc)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)

    def test_unhandled_exception_json(self):
        request = self._make_request(accept_json=True)
        exc = RuntimeError('something broke')
        response = self.middleware.process_exception(request, exc)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 500)


# ============================================================
# اختبارات RequestLoggingMiddleware
# ============================================================
class RequestLoggingMiddlewareTest(TestCase):
    """اختبار middleware تسجيل الطلبات"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestLoggingMiddleware(lambda r: None)

    def test_sets_start_time(self):
        request = self.factory.get('/test/')
        self.middleware.process_request(request)
        self.assertTrue(hasattr(request, '_start_time'))

    def test_response_without_start_time(self):
        request = self.factory.get('/test/')
        response = MagicMock()
        response.status_code = 200
        result = self.middleware.process_response(request, response)
        self.assertEqual(result, response)


# ============================================================
# اختبارات العمليات المالية الحرجة
# ============================================================
class CriticalFinancialOperationsTest(TestCase):
    """اختبارات شاملة للعمليات المالية الحرجة"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.asset_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        self.liab_type = AccountType.objects.update_or_create(
            code='liability', defaults={'name': 'خصوم', 'account_type': 'liability'}
        )[0]
        self.rev_type = AccountType.objects.update_or_create(
            code='revenue', defaults={'name': 'إيرادات', 'account_type': 'revenue'}
        )[0]
        self.exp_type = AccountType.objects.update_or_create(
            code='expense', defaults={'name': 'مصروفات', 'account_type': 'expense'}
        )[0]
        self.equity_type = AccountType.objects.update_or_create(
            code='equity', defaults={'name': 'حقوق ملكية', 'account_type': 'equity'}
        )[0]
        self.cash = Account.objects.create(code='1100', name='النقدية', account_type=self.asset_type)
        self.bank = Account.objects.create(code='1200', name='البنك', account_type=self.asset_type)
        self.revenue = Account.objects.create(code='4100', name='إيرادات مبيعات', account_type=self.rev_type)
        self.expense = Account.objects.create(code='5100', name='مصاريف إدارية', account_type=self.exp_type)
        self.supplier_acc = Account.objects.create(code='3100', name='موردون', account_type=self.liab_type)
        self.customer_acc = Account.objects.create(code='1120', name='عملاء', account_type=self.asset_type)

    def test_journal_entry_balance_integrity(self):
        """اختبار التوازن الدقيق للقيد المحاسبي"""
        lines = [
            {'account': '1100', 'debit': Decimal('5000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('5000.00')},
        ]
        entry = JournalEntryService.create_entry(
            entry_type='general', date='2024-06-15', description='اختبار التوازن', lines=lines, created_by=self.user
        )
        self.assertEqual(entry.total_debit, entry.total_credit)
        self.assertEqual(entry.total_debit, Decimal('5000.00'))

    def test_account_balance_updates_after_entry(self):
        """اختبار تحديث أرصدة الحسابات بعد الترحيل"""
        initial_cash = self.cash.current_balance
        initial_revenue = self.revenue.current_balance

        lines = [
            {'account': '1100', 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('1000.00')},
        ]
        JournalEntryService.create_entry(
            entry_type='general', date='2024-06-15', description='اختبار الأرصدة', lines=lines, created_by=self.user
        )

        self.cash.refresh_from_db()
        self.revenue.refresh_from_db()
        self.assertEqual(self.cash.current_balance, initial_cash + Decimal('1000.00'))
        self.assertEqual(self.revenue.current_balance, initial_revenue - Decimal('1000.00'))

    def test_rejects_unbalanced_entry(self):
        """اختبار رفض القيد غير المتوازن"""
        lines = [
            {'account': '1100', 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('500.00')},
        ]
        with self.assertRaises(UnbalancedEntryError):
            JournalEntryService.create_entry(
                entry_type='general', date='2024-06-15', description='قيد غير متوازن', lines=lines, created_by=self.user
            )

    def test_rejects_zero_value_entry(self):
        """اختبار رفض القيد بقيمة صفر"""
        lines = [
            {'account': '1100', 'debit': Decimal('0'), 'credit': Decimal('0')},
            {'account': '4100', 'debit': Decimal('0'), 'credit': Decimal('0')},
        ]
        with self.assertRaises(UnbalancedEntryError):
            JournalEntryService.create_entry(
                entry_type='general', date='2024-06-15', description='قيد صفري', lines=lines, created_by=self.user
            )

    def test_rejects_empty_lines(self):
        """اختبار رفض القيد بدون بنود"""
        with self.assertRaises(UnbalancedEntryError):
            JournalEntryService.create_entry(
                entry_type='general', date='2024-06-15', description='قيد فارغ', lines=[], created_by=self.user
            )

    def test_rejects_missing_account(self):
        """اختبار رفض القيد بحساب غير موجود"""
        lines = [
            {'account': '9999', 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('1000.00')},
        ]
        with self.assertRaises(AccountNotFoundError):
            JournalEntryService.create_entry(
                entry_type='general',
                date='2024-06-15',
                description='قيد بحساب مفقود',
                lines=lines,
                created_by=self.user,
            )

    def test_multi_line_balanced_entry(self):
        """اختبار قيد متعدد البنود المتوازن"""
        lines = [
            {'account': '1100', 'debit': Decimal('3000.00'), 'credit': Decimal('0.00')},
            {'account': '1200', 'debit': Decimal('2000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('5000.00')},
        ]
        entry = JournalEntryService.create_entry(
            entry_type='general', date='2024-06-15', description='قيد متعدد البنود', lines=lines, created_by=self.user
        )
        self.assertEqual(entry.total_debit, Decimal('5000.00'))
        self.assertEqual(entry.total_credit, Decimal('5000.00'))
        self.assertTrue(entry.is_posted)

    def test_account_balance_locking(self):
        """اختبار قفل الحسابات أثناء الترحيل (select_for_update)"""
        lines = [
            {'account': '1100', 'debit': Decimal('500.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('500.00')},
        ]
        entry = JournalEntryService.create_entry(
            entry_type='general', date='2024-06-15', description='اختبار القفل', lines=lines, created_by=self.user
        )
        self.cash.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('500.00'))

    def test_sequential_entries_cumulative_balances(self):
        """اختبار تراكم الأرصدة في القيود المتتابعة"""
        for i in range(5):
            amount = Decimal(str((i + 1) * 100))
            lines = [
                {'account': '1100', 'debit': amount, 'credit': Decimal('0.00')},
                {'account': '4100', 'debit': Decimal('0.00'), 'credit': amount},
            ]
            JournalEntryService.create_entry(
                entry_type='general',
                date=f'2024-06-{i + 1:02d}',
                description=f'قيد رقم {i + 1}',
                entry_number=f'TEST-{i + 1:04d}',
                lines=lines,
                created_by=self.user,
            )

        self.cash.refresh_from_db()
        self.revenue.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('1500.00'))
        self.assertEqual(self.revenue.current_balance, Decimal('-1500.00'))


class SAFE_ERROR_MESSAGESTest(TestCase):
    """اختبار رسائل الخطأ الآمنة"""

    def test_all_messages_exist(self):
        required_keys = [
            'import',
            'post',
            'backup_create',
            'backup_restore',
            'backup_export',
            'backup_import',
            'sync',
            'connection',
            'email',
            'generic',
        ]
        for key in required_keys:
            self.assertIn(key, SAFE_ERROR_MESSAGES)
            self.assertTrue(len(SAFE_ERROR_MESSAGES[key]) > 0)

    def test_no_english_error_details(self):
        for key, msg in SAFE_ERROR_MESSAGES.items():
            self.assertNotIn('str(', msg)
            self.assertNotIn('Exception', msg)
