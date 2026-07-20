from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q, F
from accounts.models import Account, JournalEntry, JournalEntryLine
from sales.models import SalesInvoice
from purchases.models import PurchaseInvoice
from treasury.models import BankTransaction, SafeTransaction
from hr.models import Salary


class AccountingErrorDetector:
    """محرك كشف الأخطاء المحاسبية - يعمل بقواعد محددة"""

    def __init__(self):
        self.errors = []

    def scan_all(self):
        """فحص شامل لجميع الأخطاء"""
        self.errors = []
        self.detect_unbalanced_entries()
        self.detect_duplicate_entries()
        self.detect_missing_accounts()
        self.detect_negative_balances()
        self.detect_posting_duplicates()
        self.detect_bank_reconciliation_diffs()
        self.detect_orphan_entries()
        return self.errors

    def detect_unbalanced_entries(self):
        """كشف القيود غير المتوازنة"""
        for entry in JournalEntry.objects.filter(is_posted=True, is_reversed=False):
            if entry.total_debit != entry.total_credit:
                diff = abs(entry.total_debit - entry.total_credit)
                self.errors.append({
                    'error_type': 'UNBALANCED_ENTRY',
                    'severity': 'critical' if diff > 1000 else 'high',
                    'title': f'قيد غير متوازن: {entry.entry_number}',
                    'description': f'القيد {entry.entry_number} بتاريخ {entry.date} غير متوازن. المدين: {entry.total_debit}، الدائن: {entry.total_credit}، الفرق: {diff}',
                    'reference_number': entry.entry_number,
                    'amount': diff,
                    'entry_date': entry.date,
                    'journal_entry_id': entry.id,
                    'raw_data': {
                        'entry_number': entry.entry_number,
                        'total_debit': str(entry.total_debit),
                        'total_credit': str(entry.total_credit),
                        'difference': str(diff),
                        'entry_type': entry.entry_type,
                    }
                })

    def detect_duplicate_entries(self):
        """كشف القيود المكررة"""
        entries = JournalEntry.objects.filter(is_posted=True).order_by('date')
        seen = {}
        for entry in entries:
            key = (entry.entry_type, entry.date, entry.total_debit, entry.total_credit, entry.description)
            if key in seen:
                self.errors.append({
                    'error_type': 'DUPLICATE_ENTRY',
                    'severity': 'high',
                    'title': f'قيد مكرر: {entry.entry_number}',
                    'description': f'القيد {entry.entry_number} مكرر للقيد {seen[key]}',
                    'reference_number': entry.entry_number,
                    'amount': entry.total_debit,
                    'entry_date': entry.date,
                    'journal_entry_id': entry.id,
                    'raw_data': {
                        'duplicate_of': seen[key],
                        'entry_number': entry.entry_number,
                    }
                })
            else:
                seen[key] = entry.entry_number

    def detect_missing_accounts(self):
        """كشف الحسابات المطلوبة المفقودة"""
        required_codes = ['1100', '1200', '1300', '1350', '2300', '3100', '3200', '3300', '4100', '5100', '5300']
        for code in required_codes:
            if not Account.objects.filter(code=code, is_active=True).exists():
                self.errors.append({
                    'error_type': 'MISSING_ACCOUNT',
                    'severity': 'critical',
                    'title': f'حساب مفقود: {code}',
                    'description': f'الحساب {code} غير موجود في دليل الحسابات. هذا الحساب مطلوب لعملية الترحيل.',
                    'affected_account_code': code,
                    'raw_data': {'required_code': code}
                })

    def detect_negative_balances(self):
        """كشف الأرصدة السالبة في الحسابات التي لا ينبغي أن تكون سالبة"""
        safe_negative_types = ['liability', 'equity', 'revenue']
        for account in Account.objects.filter(is_active=True):
            if account.account_type.account_type not in safe_negative_types:
                if account.current_balance < 0:
                    self.errors.append({
                        'error_type': 'NEGATIVE_BALANCE',
                        'severity': 'medium',
                        'title': f'رصيد سالب: {account.name} ({account.code})',
                        'description': f'الحساب {account.name} برصيد سالب {abs(account.current_balance)}. الحسابات من نوع {account.account_type.get_account_type_display()} لا ينبغي أن تكون سالبة.',
                        'affected_account_code': account.code,
                        'affected_account_name': account.name,
                        'amount': abs(account.current_balance),
                        'raw_data': {
                            'account_code': account.code,
                            'balance': str(account.current_balance),
                            'account_type': account.account_type.account_type,
                        }
                    })

    def detect_posting_duplicates(self):
        """كشف الترحيل المكرر للفواتير"""
        sales_entries = SalesInvoice.objects.filter(
            is_posted=True, journal_entry__isnull=False
        ).values('journal_entry').annotate(count=Count('id')).filter(count__gt=1)
        for item in sales_entries:
            self.errors.append({
                'error_type': 'POSTING_DUPLICATE',
                'severity': 'critical',
                'title': 'ترحيل مكرر لفاتورة مبيعات',
                'description': f'تم ترحيل فاتورة مبيعات مرتين للقيد {item["journal_entry"]}',
                'journal_entry_id': item['journal_entry'],
                'raw_data': {'invoice_count': item['count']}
            })

        purchase_entries = PurchaseInvoice.objects.filter(
            is_posted=True, journal_entry__isnull=False
        ).values('journal_entry').annotate(count=Count('id')).filter(count__gt=1)
        for item in purchase_entries:
            self.errors.append({
                'error_type': 'POSTING_DUPLICATE',
                'severity': 'critical',
                'title': 'ترحيل مكرر لفاتورة مشتريات',
                'description': f'تم ترحيل فاتورة مشتريات مرتين للقيد {item["journal_entry"]}',
                'journal_entry_id': item['journal_entry'],
                'raw_data': {'invoice_count': item['count']}
            })

    def detect_bank_reconciliation_diffs(self):
        """كشف فروقات التسوية البنكية"""
        for bank in BankTransaction.objects.values('bank').annotate(
            total_deposits=Sum('amount', filter=Q(transaction_type__in=['deposit', 'transfer_in', 'check_in'])),
            total_withdrawals=Sum('amount', filter=Q(transaction_type__in=['withdrawal', 'transfer_out', 'check_out']))
        ):
            from treasury.models import Bank
            try:
                bank_obj = Bank.objects.get(pk=bank['bank'])
                expected = (bank['total_deposits'] or Decimal('0')) - (bank['total_withdrawals'] or Decimal('0'))
                if bank_obj.current_balance != expected:
                    diff = abs(bank_obj.current_balance - expected)
                    self.errors.append({
                        'error_type': 'RECONCILIATION_DIFF',
                        'severity': 'high',
                        'title': f'فرق تسوية بنكية: {bank_obj.name}',
                        'description': f'الرصيد الفعلي للبنك {bank_obj.name} ({bank_obj.current_balance}) يختلف عن الرصيد المحسوب ({expected}). الفرق: {diff}',
                        'amount': diff,
                        'raw_data': {
                            'bank_name': bank_obj.name,
                            'actual_balance': str(bank_obj.current_balance),
                            'expected_balance': str(expected),
                            'difference': str(diff),
                        }
                    })
            except Bank.DoesNotExist:
                pass

    def detect_orphan_entries(self):
        """كشف القيود اليتيمة (قيود بدون فواتير مرتبطة)"""
        invoice_entry_ids = set()
        for inv in SalesInvoice.objects.filter(journal_entry__isnull=False).values_list('journal_entry_id', flat=True):
            invoice_entry_ids.add(str(inv))
        for inv in PurchaseInvoice.objects.filter(journal_entry__isnull=False).values_list('journal_entry_id', flat=True):
            invoice_entry_ids.add(str(inv))
        for sal in Salary.objects.filter(journal_entry__isnull=False).values_list('journal_entry_id', flat=True):
            invoice_entry_ids.add(str(sal))

        for entry in JournalEntry.objects.filter(is_posted=True).exclude(entry_type='general'):
            if str(entry.id) not in invoice_entry_ids:
                self.errors.append({
                    'error_type': 'ORPHAN_ENTRY',
                    'severity': 'low',
                    'title': f'قيد يتيم: {entry.entry_number}',
                    'description': f'القيد {entry.entry_number} من نوع {entry.get_entry_type_display()} غير مرتبط بأي فاتورة',
                    'reference_number': entry.entry_number,
                    'journal_entry_id': entry.id,
                    'raw_data': {'entry_type': entry.entry_type}
                })

    def detect_specific_unbalanced_sales(self):
        """كشف عدم توازن قيود المبيعات مع الخصم"""
        errors = []
        for invoice in SalesInvoice.objects.filter(is_posted=True, discount_amount__gt=0):
            if invoice.journal_entry:
                entry = invoice.journal_entry
                if entry.total_debit != entry.total_credit:
                    errors.append({
                        'error_type': 'SALES_DISCOUNT_UNBALANCED',
                        'severity': 'critical',
                        'title': f'فاتورة مبيعات غير متوازنة مع خصم: {invoice.invoice_number}',
                        'description': f'فاتورة {invoice.invoice_number} بها خصم {invoice.discount_amount} لكن القيد المحاسبي لا يعكس ذلك بشكل صحيح.',
                        'reference_number': invoice.invoice_number,
                        'amount': invoice.discount_amount,
                        'raw_data': {
                            'invoice_number': invoice.invoice_number,
                            'discount': str(invoice.discount_amount),
                            'debit': str(entry.total_debit),
                            'credit': str(entry.total_credit),
                        }
                    })
        return errors

    def detect_specific_unbalanced_purchases(self):
        """كشف عدم توازن قيود المشتريات مع الخصم والتحصيل"""
        errors = []
        for invoice in PurchaseInvoice.objects.filter(is_posted=True).filter(
            Q(discount_amount__gt=0) | Q(withholding_tax_amount__gt=0)
        ):
            if invoice.journal_entry:
                entry = invoice.journal_entry
                if entry.total_debit != entry.total_credit:
                    errors.append({
                        'error_type': 'PURCHASE_DISCOUNT_UNBALANCED',
                        'severity': 'critical',
                        'title': f'فاتورة مشتريات غير متوازنة: {invoice.invoice_number}',
                        'description': f'فاتورة {invoice.invoice_number} بها خصم/تحصيل لكن القيد غير متوازن.',
                        'reference_number': invoice.invoice_number,
                        'amount': abs(entry.total_debit - entry.total_credit),
                        'raw_data': {
                            'invoice_number': invoice.invoice_number,
                            'discount': str(invoice.discount_amount),
                            'withholding': str(invoice.withholding_tax_amount),
                            'debit': str(entry.total_debit),
                            'credit': str(entry.total_credit),
                        }
                    })
        return errors

    def detect_specific_unbalanced_salaries(self):
        """كشف عدم توازن قيود الرواتب"""
        errors = []
        for salary in Salary.objects.filter(is_paid=True, journal_entry__isnull=False):
            if salary.deductions > 0:
                entry = salary.journal_entry
                if entry.total_debit != entry.total_credit:
                    errors.append({
                        'error_type': 'SALARY_DEDUCTIONS_UNBALANCED',
                        'severity': 'critical',
                        'title': f'قيد راتب غير متوازن: {salary.employee.full_name}',
                        'description': f'راتب {salary.employee.full_name} ({salary.month}/{salary.year}) به خصومات {salary.deductions} لكن القيد غير متوازن.',
                        'amount': salary.deductions,
                        'raw_data': {
                            'employee': salary.employee.full_name,
                            'month': salary.month,
                            'year': salary.year,
                            'deductions': str(salary.deductions),
                            'debit': str(entry.total_debit),
                            'credit': str(entry.total_credit),
                        }
                    })
        return errors
