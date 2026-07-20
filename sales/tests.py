from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Account, AccountType
from purchases.models import Product, ProductCategory

from .models import Customer, SalesInvoice, SalesInvoiceLine


class CustomerModelTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(code='C001', name='عميل تجريبي', phone='01234567890')

    def test_customer_creation(self):
        self.assertEqual(str(self.customer), 'C001 - عميل تجريبي')

    def test_customer_default_balance(self):
        self.assertEqual(self.customer.current_balance, Decimal('0.00'))


class SalesInvoiceCalculationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.customer = Customer.objects.create(code='C001', name='عميل تجريبي')

        asset_type = AccountType.objects.update_or_create(
            code='asset', defaults={'name': 'أصول', 'account_type': 'asset'}
        )[0]
        revenue_type = AccountType.objects.update_or_create(
            code='revenue', defaults={'name': 'إيرادات', 'account_type': 'revenue'}
        )[0]
        expense_type = AccountType.objects.update_or_create(
            code='expense', defaults={'name': 'مصروفات', 'account_type': 'expense'}
        )[0]

        Account.objects.create(code='1100', name='العملاء', account_type=asset_type)
        Account.objects.create(code='1200', name='المخزون', account_type=asset_type)
        Account.objects.create(code='3200', name='ضريبة المبيعات', account_type=expense_type)
        Account.objects.create(code='4100', name='إيرادات المبيعات', account_type=revenue_type)
        Account.objects.create(code='5100', name='تكلفة المبيعات', account_type=expense_type)

        self.category = ProductCategory.objects.create(name='فئة اختبار')
        self.product = Product.objects.create(
            code='P001',
            name='منتج اختبار',
            category=self.category,
            purchase_price=Decimal('50.00'),
            selling_price=Decimal('100.00'),
        )

    def _create_invoice(self, vat_enabled=True, withholding_tax=0, discount=0):
        invoice = SalesInvoice.objects.create(
            invoice_number='INV-001',
            customer=self.customer,
            date=date.today(),
            is_tax_invoice=vat_enabled,
            withholding_tax_type=withholding_tax,
            discount_amount=Decimal(str(discount)),
            created_by=self.user,
        )
        SalesInvoiceLine.objects.create(
            invoice=invoice,
            product=self.product,
            quantity=Decimal('2'),
            unit_price=Decimal('100.00'),
            cost_price=Decimal('50.00'),
        )
        invoice.calculate_totals()
        return invoice

    def test_basic_invoice_calculation(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice.subtotal, Decimal('200.00'))
        self.assertEqual(invoice.vat_amount, Decimal('28.00'))
        self.assertEqual(invoice.total_amount, Decimal('228.00'))
        self.assertEqual(invoice.cost_of_goods, Decimal('100.00'))
        self.assertEqual(invoice.gross_profit, Decimal('100.00'))

    def test_invoice_without_vat(self):
        invoice = self._create_invoice(vat_enabled=False)
        self.assertEqual(invoice.vat_amount, Decimal('0.00'))
        self.assertEqual(invoice.total_amount, Decimal('200.00'))

    def test_invoice_with_withholding_tax(self):
        invoice = self._create_invoice(withholding_tax=1)
        self.assertEqual(invoice.subtotal, Decimal('200.00'))
        self.assertEqual(invoice.withholding_tax_amount, Decimal('2.00'))

    def test_invoice_with_discount(self):
        invoice = self._create_invoice(discount=10)
        self.assertEqual(invoice.total_amount, Decimal('218.00'))

    def test_remaining_amount_calculation(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice.remaining_amount, Decimal('228.00'))

    def test_multi_line_invoice(self):
        invoice = SalesInvoice.objects.create(
            invoice_number='INV-002', customer=self.customer, date=date.today(), created_by=self.user
        )
        SalesInvoiceLine.objects.create(
            invoice=invoice, product=self.product, quantity=Decimal('1'), unit_price=Decimal('100.00')
        )
        SalesInvoiceLine.objects.create(
            invoice=invoice, product=self.product, quantity=Decimal('3'), unit_price=Decimal('80.00')
        )
        invoice.calculate_totals()
        self.assertEqual(invoice.subtotal, Decimal('340.00'))
        self.assertEqual(invoice.vat_amount, Decimal('47.60'))
        self.assertEqual(invoice.total_amount, Decimal('387.60'))

    def test_line_total_price(self):
        invoice = SalesInvoice.objects.create(
            invoice_number='INV-003', customer=self.customer, date=date.today(), created_by=self.user
        )
        line = SalesInvoiceLine.objects.create(
            invoice=invoice, product=self.product, quantity=Decimal('5'), unit_price=Decimal('40.00')
        )
        self.assertEqual(line.total_price, Decimal('200.00'))
        self.assertEqual(line.cost_total, Decimal('250.00'))
        self.assertTrue(line.profit < 0)
