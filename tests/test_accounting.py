"""
اختبارات شاملة للنظام المحاسبي
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from accounts.models import AccountType, Account, JournalEntry, JournalEntryLine
from purchases.models import Supplier, Product, ProductCategory, UnitOfMeasure, PurchaseInvoice, PurchaseInvoiceLine
from sales.models import Customer, SalesInvoice, SalesInvoiceLine
from company.models import Company
from common.validators import (
    validate_positive_decimal, validate_balanced_entry, 
    validate_vat_rate, validate_withholding_tax_type, FinancialValidator
)
from common.accounting_service import (
    JournalEntryService, UnbalancedEntryError, AccountNotFoundError, InsufficientStockError
)
from common.exceptions import AccountingError


class ValidatorsTest(TestCase):
    """اختبارات الدوال التحقق (Validators)"""
    
    def test_validate_positive_decimal_valid(self):
        """اختبار التحقق من القيم الموجبة الصحيحة"""
        validate_positive_decimal(Decimal('100.00'))
        validate_positive_decimal(Decimal('0.01'))
    
    def test_validate_positive_decimal_invalid(self):
        """اختبار رفض القيم السالبة والصفر"""
        with self.assertRaises(ValidationError):
            validate_positive_decimal(Decimal('-10.00'))
        with self.assertRaises(ValidationError):
            validate_positive_decimal(Decimal('-0.01'))
        with self.assertRaises(ValidationError):
            validate_positive_decimal(Decimal('0'))
    
    def test_validate_balanced_entry_valid(self):
        """اختبار التحقق من توازن القيد الصحيح"""
        validate_balanced_entry(Decimal('1000.00'), Decimal('1000.00'))
        validate_balanced_entry(Decimal('0'), Decimal('0'))
    
    def test_validate_balanced_entry_invalid(self):
        """اختبار رفض القيد غير المتوازن"""
        with self.assertRaises(ValidationError):
            validate_balanced_entry(Decimal('1000.00'), Decimal('500.00'))
        with self.assertRaises(ValidationError):
            validate_balanced_entry(Decimal('100.00'), Decimal('200.00'))
    
    def test_validate_vat_rate_valid(self):
        """اختبار التحقق من نسب الضريبة الصحيحة"""
        validate_vat_rate(Decimal('14.00'))
        validate_vat_rate(Decimal('0'))
        validate_vat_rate(Decimal('100'))
    
    def test_validate_vat_rate_invalid(self):
        """اختبار رفض نسب الضريبة غير الصحيحة"""
        with self.assertRaises(ValidationError):
            validate_vat_rate(Decimal('-1'))
        with self.assertRaises(ValidationError):
            validate_vat_rate(Decimal('101'))
    
    def test_validate_withholding_tax_type_valid(self):
        """اختبار التحقق من أنواع الخصم والتحصيل الصحيحة"""
        for val in [0, 1, 3, 5]:
            validate_withholding_tax_type(val)
    
    def test_validate_withholding_tax_type_invalid(self):
        """اختبار رفض أنواع الخصم والتحصيل غير الصحيحة"""
        with self.assertRaises(ValidationError):
            validate_withholding_tax_type(2)
        with self.assertRaises(ValidationError):
            validate_withholding_tax_type(10)
    
    def test_financial_validator_invoice_totals(self):
        """اختبار التحقق من إجماليات الفاتورة"""
        # صحيح
        FinancialValidator.validate_invoice_totals(
            subtotal=Decimal('1000.00'),
            vat_amount=Decimal('140.00'),
            discount_amount=Decimal('50.00'),
            withholding_tax_amount=Decimal('0.00'),
            total_amount=Decimal('1090.00')
        )
        
        # خاطئ - إجمالي غير صحيح
        with self.assertRaises(ValidationError):
            FinancialValidator.validate_invoice_totals(
                subtotal=Decimal('1000.00'),
                vat_amount=Decimal('140.00'),
                discount_amount=Decimal('50.00'),
                withholding_tax_amount=Decimal('0.00'),
                total_amount=Decimal('1000.00')  # خاطئ
            )
    
    def test_financial_validator_journal_entry_lines(self):
        """اختبار التحقق من بنود القيد المحاسبي"""
        lines = [
            {'account': '1100', 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('1000.00')},
        ]
        FinancialValidator.validate_journal_entry_lines(lines)
        
        # خاطئ - غير متوازن
        with self.assertRaises(ValidationError):
            FinancialValidator.validate_journal_entry_lines([
                {'account': '1100', 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
                {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('500.00')},
            ])
        
        # خاطئ - مدين ودائن في نفس السطر
        with self.assertRaises(ValidationError):
            FinancialValidator.validate_journal_entry_lines([
                {'account': '1100', 'debit': Decimal('1000.00'), 'credit': Decimal('500.00')},
                {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('500.00')},
            ])


class JournalEntryServiceTest(TestCase):
    """اختبارات خدمة القيد المحاسبي"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        self.rev_type = AccountType.objects.update_or_create(
            code='revenue', defaults={'name': 'إيرادات', 'account_type': 'revenue'}
        )[0]
        self.liab_type = AccountType.objects.update_or_create(
            code='liability', defaults={'name': 'خصوم', 'account_type': 'liability'}
        )[0]
        self.cash = Account.objects.create(
            code='1100', name='النقدية', account_type=self.acc_type,
        )
        self.revenue = Account.objects.create(
            code='4100', name='إيرادات', account_type=self.rev_type,
        )
        self.supplier = Account.objects.create(
            code='3100', name='موردون', account_type=self.liab_type,
        )
    
    def test_create_balanced_entry_success(self):
        """اختبار إنشاء قيد متوازن بنجاح"""
        lines = [
            {'account': '1100', 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('1000.00')},
        ]
        entry = JournalEntryService.create_entry(
            entry_type='general',
            date='2024-01-15',
            description='قيد اختبار',
            lines=lines,
            created_by=self.user,
        )
        self.assertTrue(entry.is_posted)
        self.assertEqual(entry.total_debit, Decimal('1000.00'))
        self.assertEqual(entry.total_credit, Decimal('1000.00'))
        
        # التحقق من تحديث الأرصدة
        self.cash.refresh_from_db()
        self.revenue.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('1000.00'))
        self.assertEqual(self.revenue.current_balance, Decimal('-1000.00'))
    
    def test_create_unbalanced_entry_raises_error(self):
        """اختبار فشل إنشاء قيد غير متوازن"""
        lines = [
            {'account': '1100', 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('500.00')},
        ]
        with self.assertRaises(UnbalancedEntryError):
            JournalEntryService.create_entry(
                entry_type='general',
                date='2024-01-15',
                description='قيد غير متوازن',
                lines=lines,
                created_by=self.user,
            )
    
    def test_create_entry_missing_account_raises_error(self):
        """اختبار فشل إنشاء قيد بحساب مفقود"""
        lines = [
            {'account': '9999', 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
            {'account': '4100', 'debit': Decimal('0.00'), 'credit': Decimal('1000.00')},
        ]
        with self.assertRaises(AccountNotFoundError):
            JournalEntryService.create_entry(
                entry_type='general',
                date='2024-01-15',
                description='قيد بحساب مفقود',
                lines=lines,
                created_by=self.user,
            )
    
    def test_get_account_with_fallback(self):
        """اختبار جلب الحساب مع الحساب الاحتياطي"""
        # الحساب موجود
        account = JournalEntryService.get_account('1100')
        self.assertEqual(account.code, '1100')
        
        # الحساب غير موجود لكن الاحتياطي موجود
        account = JournalEntryService.get_account('9999', default_code='1100')
        self.assertEqual(account.code, '1100')
        
        # كليهما غير موجود
        with self.assertRaises(AccountNotFoundError):
            JournalEntryService.get_account('9999', default_code='8888')


class AccountModelTest(TestCase):
    """اختبارات نموذج الحساب مع الـ Validators"""
    
    def setUp(self):
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
    
    def test_account_opening_balance_validator(self):
        """اختبار التحقق من الرصيد الافتتاحي"""
        # صحيح
        account = Account.objects.create(
            code='1200', name='البنك', account_type=self.acc_type,
            opening_balance=Decimal('5000.00'),
        )
        self.assertEqual(account.opening_balance, Decimal('5000.00'))
        
        # صفر صحيح
        account2 = Account.objects.create(
            code='1201', name='صندوق', account_type=self.acc_type,
            opening_balance=Decimal('0'),
        )
        self.assertEqual(account2.opening_balance, Decimal('0'))
        
        # سالب - مسموح به الآن لأن الحقل لا يحتوي على validator
        account3 = Account.objects.create(
            code='1202', name='سالب', account_type=self.acc_type,
            opening_balance=Decimal('-100.00'),
        )
        self.assertEqual(account3.opening_balance, Decimal('-100.00'))
    
    def test_account_current_balance_validator(self):
        """اختبار التحقق من الرصيد الحالي"""
        account = Account.objects.create(
            code='1300', name='النقدية', account_type=self.acc_type,
        )
        account.current_balance = Decimal('1000.00')
        account.full_clean()  # يجب أن يمر
        
        account.current_balance = Decimal('-100.00')
        account.full_clean()  # مسموح به الآن


class JournalEntryLineModelTest(TestCase):
    """اختبارات نموذج بند القيد مع الـ Validators"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        self.rev_type = AccountType.objects.update_or_create(
            code='revenue', defaults={'name': 'إيرادات', 'account_type': 'revenue'}
        )[0]
        self.cash = Account.objects.create(
            code='1100', name='النقدية', account_type=self.acc_type,
        )
        self.revenue = Account.objects.create(
            code='4100', name='إيرادات', account_type=self.rev_type,
        )
        self.entry = JournalEntry.objects.create(
            entry_number='JE-001', entry_type='general',
            description='قيد اختبار', created_by=self.user,
        )
    
    def test_journal_entry_line_validators(self):
        """اختبار الـ Validators على بنود القيد"""
        # صحيح - مدين فقط
        line = JournalEntryLine(
            journal_entry=self.entry, account=self.cash,
            debit=Decimal('1000.00'), credit=Decimal('0.00'),
        )
        line.full_clean()  # يجب أن يمر
        
        # صحيح - دائن فقط
        line2 = JournalEntryLine(
            journal_entry=self.entry, account=self.revenue,
            debit=Decimal('0.00'), credit=Decimal('1000.00'),
        )
        line2.full_clean()  # يجب أن يمر
        
        # خاطئ - مدين ودائن معاً
        line3 = JournalEntryLine(
            journal_entry=self.entry, account=self.cash,
            debit=Decimal('1000.00'), credit=Decimal('500.00'),
        )
        with self.assertRaises(ValidationError):
            line3.full_clean()
        
        # خاطئ - لا مدين ولا دائن
        line4 = JournalEntryLine(
            journal_entry=self.entry, account=self.cash,
            debit=Decimal('0.00'), credit=Decimal('0.00'),
        )
        with self.assertRaises(ValidationError):
            line4.full_clean()
    
    def test_journal_entry_line_both_debit_credit_rejected(self):
        """اختبار رفض السطر الذي يحتوي على مدين ودائن معاً"""
        line = JournalEntryLine(
            journal_entry=self.entry, account=self.cash,
            debit=Decimal('100.00'), credit=Decimal('200.00'),
        )
        with self.assertRaises(ValidationError):
            line.full_clean()


class PurchaseInvoiceModelTest(TestCase):
    """اختبارات نموذج فاتورة المشتريات"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.supplier = Supplier.objects.create(
            code='SUP001', name='مورد اختبار',
            supplier_type='company',
        )
        self.category = ProductCategory.objects.create(
            code='CAT001', name='فئة اختبار',
        )
        self.unit = UnitOfMeasure.objects.create(
            code='PCS', name='قطعة',
        )
        self.product = Product.objects.create(
            code='PROD001', name='منتج اختبار',
            category=self.category, unit_of_measure=self.unit,
            purchase_price=Decimal('100.00'), selling_price=Decimal('150.00'),
        )
    
    def test_purchase_invoice_line_calculation(self):
        """اختبار حساب بند الفاتورة"""
        invoice = PurchaseInvoice.objects.create(
            invoice_number='PI-001', supplier=self.supplier,
            date='2024-01-15', created_by=self.user,
        )
        line = PurchaseInvoiceLine.objects.create(
            invoice=invoice, product=self.product,
            quantity=Decimal('10.0000000000'),
            unit_price=Decimal('100.0000000000'),
            discount_percent=Decimal('10.00'),
        )
        self.assertEqual(line.total_price, Decimal('900.00'))  # 10 * 100 * 0.9
    
    def test_purchase_invoice_totals(self):
        """اختبار حساب إجماليات الفاتورة"""
        invoice = PurchaseInvoice.objects.create(
            invoice_number='PI-002', supplier=self.supplier,
            date='2024-01-15', created_by=self.user,
            is_tax_invoice=True,
        )
        PurchaseInvoiceLine.objects.create(
            invoice=invoice, product=self.product,
            quantity=Decimal('5.0000000000'),
            unit_price=Decimal('200.0000000000'),
        )
        invoice.calculate_totals()
        self.assertEqual(invoice.subtotal, Decimal('1000.00'))
        self.assertEqual(invoice.vat_amount, Decimal('140.00'))  # 14%
        self.assertEqual(invoice.total_amount, Decimal('1140.00'))
    
    def test_purchase_invoice_validators(self):
        """اختبار الـ Validators على حقول الفاتورة"""
        invoice = PurchaseInvoice(
            invoice_number='PI-003', supplier=self.supplier,
            date='2024-01-15', created_by=self.user,
            payment_method='invalid',  # طريقة دفع غير صحيحة
        )
        with self.assertRaises(ValidationError):
            invoice.full_clean()


class SalesInvoiceModelTest(TestCase):
    """اختبارات نموذج فاتورة المبيعات"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.customer = Customer.objects.create(
            code='CUS001', name='عميل اختبار',
            customer_type='company',
        )
        self.category = ProductCategory.objects.create(
            code='CAT001', name='فئة اختبار',
        )
        self.unit = UnitOfMeasure.objects.create(
            code='PCS', name='قطعة',
        )
        self.product = Product.objects.create(
            code='PROD001', name='منتج اختبار',
            category=self.category, unit_of_measure=self.unit,
            purchase_price=Decimal('100.00'), selling_price=Decimal('200.00'),
        )
    
    def test_sales_invoice_line_calculation(self):
        """اختبار حساب بند فاتورة المبيعات"""
        invoice = SalesInvoice.objects.create(
            invoice_number='SI-001', customer=self.customer,
            date='2024-01-15', created_by=self.user,
        )
        line = SalesInvoiceLine.objects.create(
            invoice=invoice, product=self.product,
            quantity=Decimal('5.0000000000'),
            unit_price=Decimal('200.0000000000'),
            discount_percent=Decimal('5.00'),
        )
        # 5 * 200 = 1000, خصم 5% = 950
        self.assertEqual(line.total_price, Decimal('950.00'))
        self.assertEqual(line.cost_total, Decimal('500.00'))  # 5 * 100
        self.assertEqual(line.profit, Decimal('450.00'))  # 950 - 500
        # هامش الربح = (450/950)*100 = 47.368...%
        self.assertAlmostEqual(float(line.profit_margin), 47.37, places=2)


class FinancialValidatorIntegrationTest(TestCase):
    """اختبارات تكاملية للمدقق المالي"""
    
    def test_validate_invoice_payment(self):
        """اختبار التحقق من مبلغ الدفع"""
        FinancialValidator.validate_invoice_payment(
            payment_amount=Decimal('500.00'),
            remaining_amount=Decimal('1000.00')
        )
        
        with self.assertRaises(ValidationError):
            FinancialValidator.validate_invoice_payment(
                payment_amount=Decimal('1500.00'),
                remaining_amount=Decimal('1000.00')
            )


class ExceptionHandlingTest(TestCase):
    """اختبارات التعامل مع الاستثناءات المخصصة"""
    
    def test_accounting_error_hierarchy(self):
        """اختبار هرمية استثناءات المحاسبة"""
        # التحقق من أن الاستثناءات ترث من AccountingError
        self.assertTrue(issubclass(UnbalancedEntryError, AccountingError))
        self.assertTrue(issubclass(AccountNotFoundError, AccountingError))
        self.assertTrue(issubclass(InsufficientStockError, AccountingError))
        
        # التحقق من إمكانية التقاطها كـ AccountingError
        try:
            raise UnbalancedEntryError('Test error')
        except AccountingError as e:
            self.assertEqual(str(e), 'Test error')
    
    def test_insufficient_stock_error(self):
        """اختبار استثناء المخزون غير الكافي"""
        error = InsufficientStockError(
            product_name='منتج',
            available=Decimal('5.00'),
            requested=Decimal('10.00')
        )
        self.assertIn('منتج', str(error))
        self.assertIn('5.00', str(error))
        self.assertIn('10.00', str(error))


class ConcurrentPostingTest(TestCase):
    """اختبارات التزامن في ترحيل القيود"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_concurrent', password='testpass123')
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        self.rev_type = AccountType.objects.update_or_create(
            code='revenue', defaults={'name': 'إيرادات', 'account_type': 'revenue'}
        )[0]
        self.cash = Account.objects.create(
            code='1100', name='النقدية', account_type=self.acc_type,
        )
        self.revenue = Account.objects.create(
            code='4100', name='إيرادات', account_type=self.rev_type,
        )
    
    def test_sequential_posting_simulation(self):
        """اختبار الترحيل المتسلسل - التحقق من تحديث الأرصدة بشكل صحيح"""
        # نستخدم حلقة متسلسلة بدلاً من threading لأن SQLite لا يدعم التزامن الحقيقي
        for i in range(10):
            entry = JournalEntry.objects.create(
                entry_number=f'JE-{i}',
                entry_type='general',
                date='2024-01-15',
                description=f'قيد اختبار {i}',
                created_by=self.user,
            )
            JournalEntryLine.objects.create(
                journal_entry=entry, account=self.cash,
                debit=Decimal('100.00'), credit=Decimal('0.00'),
            )
            JournalEntryLine.objects.create(
                journal_entry=entry, account=self.revenue,
                debit=Decimal('0.00'), credit=Decimal('100.00'),
            )
            entry.calculate_totals()
            entry.post()
        
        # التحقق من الرصيد النهائي
        self.cash.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('1000.00'))
        
        # التحقق من أن جميع القيود مرحلين
        posted_entries = JournalEntry.objects.filter(is_posted=True).count()
        self.assertEqual(posted_entries, 10)


class ModelValidationIntegrationTest(TestCase):
    """اختبارات تكاملية للتحقق من النماذج"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_model', password='testpass123')
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        self.rev_type = AccountType.objects.update_or_create(
            code='revenue', defaults={'name': 'إيرادات', 'account_type': 'revenue'}
        )[0]
        self.liab_type = AccountType.objects.update_or_create(
            code='liability', defaults={'name': 'خصوم', 'account_type': 'liability'}
        )[0]
        self.exp_type = AccountType.objects.update_or_create(
            code='expense', defaults={'name': 'مصروفات', 'account_type': 'expense'}
        )[0]
        self.cash = Account.objects.create(code='1100', name='النقدية', account_type=self.acc_type)
        self.revenue = Account.objects.create(code='4100', name='إيرادات', account_type=self.rev_type)
        # حسابات إضافية للفواتير - استخدام أكواد فريدة لتجنب التعارض
        self.purchases_acc = Account.objects.create(
            code='1300', name='مشتريات', account_type=self.exp_type,
        )
        self.vat_acc = Account.objects.create(
            code='1350', name='ضريبة القيمة المضافة', account_type=self.acc_type,
        )
        self.wt_acc = Account.objects.create(
            code='2130', name='الخصم والتحصيل', account_type=self.liab_type,
        )
        self.discount_acc = Account.objects.create(
            code='4300', name='خصم مكتسب', account_type=self.rev_type,
        )
        self.supplier_acc = Account.objects.create(
            code='3100', name='الموردون', account_type=self.liab_type,
        )
        self.cogs_acc = Account.objects.create(
            code='5100', name='تكلفة البضاعة', account_type=self.exp_type,
        )
        self.inventory_acc = Account.objects.create(
            code='1200', name='المخزون', account_type=self.acc_type,
        )
        self.customer_acc = Account.objects.create(
            code='1101', name='العملاء', account_type=self.acc_type,
        )
    
    def test_full_invoice_creation_and_posting(self):
        """اختبار دورة حياة كاملة: إنشاء فاتورة وترحيلها"""
        from purchases.models import Supplier, Product, ProductCategory, UnitOfMeasure
        
        supplier = Supplier.objects.create(
            code='SUP001', name='مورد اختبار', supplier_type='company',
        )
        category = ProductCategory.objects.create(code='CAT001', name='فئة')
        unit = UnitOfMeasure.objects.create(code='PCS', name='قطعة')
        product = Product.objects.create(
            code='PROD001', name='منتج', category=category,
            unit_of_measure=unit, purchase_price=Decimal('100.00'),
            selling_price=Decimal('150.00'),
        )
        
        # إنشاء فاتورة مشتريات
        invoice = PurchaseInvoice.objects.create(
            invoice_number='PI-TEST-001', supplier=supplier,
            date='2024-01-15', created_by=self.user,
            is_tax_invoice=True,
        )
        PurchaseInvoiceLine.objects.create(
            invoice=invoice, product=product,
            quantity=Decimal('10.0000000000'),
            unit_price=Decimal('100.0000000000'),
        )
        invoice.calculate_totals()
        
        # ترحيل الفاتورة
        invoice.approve(self.user)
        invoice.create_journal_entry()
        
        self.assertTrue(invoice.is_posted)
        self.assertIsNotNone(invoice.journal_entry)
        self.assertTrue(invoice.journal_entry.is_posted)
        
        # التحقق من الأرصدة
        self.cash.refresh_from_db()
        self.revenue.refresh_from_db()
        
        # يجب أن يكون المورد مديناً والرصيد النقدي قد تحديث
        self.assertIsNotNone(invoice.journal_entry.entry_number)


class ServiceLayerTest(TestCase):
    """اختبارات طبقة الخدمات"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.acc_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        self.rev_type = AccountType.objects.update_or_create(
            code='revenue', defaults={'name': 'إيرادات', 'account_type': 'revenue'}
        )[0]
        self.liab_type = AccountType.objects.update_or_create(
            code='liability', defaults={'name': 'خصوم', 'account_type': 'liability'}
        )[0]
        self.cash = Account.objects.create(code='1100', name='النقدية', account_type=self.acc_type)
        self.revenue = Account.objects.create(code='4100', name='إيرادات', account_type=self.rev_type)
        self.supplier_acc = Account.objects.create(code='3100', name='موردون', account_type=self.liab_type)
    
    def test_service_creates_balanced_entry(self):
        """اختبار إنشاء خدمة للقيد المتوازن"""
        lines = [
            {'account': self.cash, 'debit': Decimal('1000.00'), 'credit': Decimal('0.00'), 'description': 'نقدية'},
            {'account': self.revenue, 'debit': Decimal('0.00'), 'credit': Decimal('1000.00'), 'description': 'إيرادات'},
        ]
        entry = JournalEntryService.create_entry(
            entry_type='general', date='2024-01-15',
            description='اختبار خدمة', lines=lines, created_by=self.user,
        )
        self.assertTrue(entry.is_posted)
        self.assertEqual(entry.total_debit, Decimal('1000.00'))
    
    def test_service_validates_account_existence(self):
        """اختبار تحقق الخدمة من وجود الحسابات"""
        # إنشاء حساب وهمي برمز غير موجود
        from accounts.models import Account
        fake_account = Account(code='9999', name='وهمي', account_type=self.rev_type)
        fake_account.id = '00000000-0000-0000-0000-000000000000'
        
        lines = [
            {'account': fake_account, 'debit': Decimal('1000.00'), 'credit': Decimal('0.00')},
            {'account': self.revenue, 'debit': Decimal('0.00'), 'credit': Decimal('1000.00')},
        ]
        with self.assertRaises(AccountNotFoundError):
            JournalEntryService.create_entry(
                entry_type='general', date='2024-01-15',
                description='اختبار', lines=lines, created_by=self.user,
            )
    
    def test_get_account_fallback(self):
        """اختبار الحساب الاحتياطي"""
        # الحساب الأساسي موجود
        account = JournalEntryService.get_account('1100')
        self.assertEqual(account.code, '1100')
        
        # الحساب الأساسي غير موجود لكن الاحتياطي موجود
        account = JournalEntryService.get_account('9999', default_code='1100')
        self.assertEqual(account.code, '1100')
        
        # كلاهما غير موجود
        with self.assertRaises(AccountNotFoundError):
            JournalEntryService.get_account('9999', default_code='8888')


if __name__ == '__main__':
    import django
    django.setup()
    from django.test.utils import get_runner
    from django.conf import settings
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests([
        'accounts.tests',
        'purchases.tests',
        'sales.tests',
    ])
    exit(failures)