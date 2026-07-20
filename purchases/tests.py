from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import AccountType, Account
from .forms import ProductForm
from .models import (ProductCategory, Product, Supplier, PurchaseInvoice, PurchaseInvoiceLine,
                     UnitOfMeasure, CatalogSettings)


class ProductModelTest(TestCase):
    def setUp(self):
        self.category = ProductCategory.objects.create(code='CAT-001', name='فئة اختبار')
        self.product = Product.objects.create(
            code='P001', name='منتج اختبار',
            category=self.category,
            purchase_price=Decimal('50.00'),
            selling_price=Decimal('100.00'),
        )

    def test_product_creation(self):
        self.assertEqual(str(self.product), 'P001 - منتج اختبار')

    def test_profit_margin(self):
        self.assertEqual(self.product.profit_margin, Decimal('100.00'))

    def test_stock_value(self):
        self.product.current_stock = Decimal('10')
        self.product.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_value, Decimal('500.00'))


class PurchaseInvoiceCalculationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.supplier = Supplier.objects.create(code='S001', name='مورد تجريبي')

        asset_type = AccountType.objects.update_or_create(code='asset', defaults={'name': 'أصول', 'account_type': 'asset'})[0]
        expense_type = AccountType.objects.update_or_create(code='expense', defaults={'name': 'مصروفات', 'account_type': 'expense'})[0]

        Account.objects.create(code='1300', name='المشتريات', account_type=expense_type)
        Account.objects.create(code='1350', name='ضريبة المشتريات', account_type=expense_type)

        self.category = ProductCategory.objects.create(code='CAT-001', name='فئة اختبار')
        self.product = Product.objects.create(
            code='P001', name='منتج اختبار',
            category=self.category,
            purchase_price=Decimal('50.00'),
            selling_price=Decimal('100.00'),
        )

    def _create_invoice(self, vat_enabled=True, withholding_tax=0, discount=0):
        invoice = PurchaseInvoice.objects.create(
            invoice_number='PINV-001',
            supplier=self.supplier,
            date=date.today(),
            is_tax_invoice=vat_enabled,
            withholding_tax_type=withholding_tax,
            discount_amount=Decimal(str(discount)),
            created_by=self.user,
        )
        PurchaseInvoiceLine.objects.create(
            invoice=invoice, product=self.product,
            quantity=Decimal('10'), unit_price=Decimal('50.00'),
        )
        invoice.calculate_totals()
        return invoice

    def test_basic_invoice_calculation(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice.subtotal, Decimal('500.00'))
        self.assertEqual(invoice.vat_amount, Decimal('70.00'))
        self.assertEqual(invoice.total_amount, Decimal('570.00'))
        self.assertEqual(invoice.remaining_amount, Decimal('570.00'))

    def test_invoice_without_vat(self):
        invoice = self._create_invoice(vat_enabled=False)
        self.assertEqual(invoice.vat_amount, Decimal('0.00'))
        self.assertEqual(invoice.total_amount, Decimal('500.00'))

    def test_invoice_with_withholding_tax(self):
        invoice = self._create_invoice(withholding_tax=1)
        self.assertEqual(invoice.withholding_tax_amount, Decimal('5.00'))

    def test_invoice_with_discount(self):
        invoice = self._create_invoice(discount=20)
        self.assertEqual(invoice.total_amount, Decimal('550.00'))

    def test_remaining_amount_after_payment(self):
        invoice = self._create_invoice()
        invoice.paid_amount = Decimal('200.00')
        invoice.calculate_totals()
        self.assertEqual(invoice.remaining_amount, Decimal('370.00'))

    def test_multi_line_invoice(self):
        invoice = PurchaseInvoice.objects.create(
            invoice_number='PINV-002', supplier=self.supplier,
            date=date.today(),
            created_by=self.user,
        )
        PurchaseInvoiceLine.objects.create(
            invoice=invoice, product=self.product,
            quantity=Decimal('5'), unit_price=Decimal('50.00'),
        )
        PurchaseInvoiceLine.objects.create(
            invoice=invoice, product=self.product,
            quantity=Decimal('3'), unit_price=Decimal('70.00'),
        )
        invoice.calculate_totals()
        self.assertEqual(invoice.subtotal, Decimal('460.00'))


class UnitOfMeasureTest(TestCase):
    def test_unit_creation_and_str(self):
        unit = UnitOfMeasure.objects.create(code='PC', name='قطعة', symbol='pc')
        self.assertEqual(str(unit), 'قطعة (pc)')

    def test_conversion_to_base(self):
        kg = UnitOfMeasure.objects.create(code='KG', name='كيلوجرام', symbol='kg')
        g = UnitOfMeasure.objects.create(code='G', name='جرام', symbol='g',
                                         base_unit=kg, conversion_factor=Decimal('0.001'))
        # 1000 جرام = 1 كيلوجرام
        self.assertEqual(g.to_base(Decimal('1000')), Decimal('1'))
        # تحويل 500 جرام إلى كيلوجرام
        self.assertEqual(g.convert_to(Decimal('500'), kg), Decimal('0.5'))

    def test_product_links_unit_and_syncs_legacy_field(self):
        unit = UnitOfMeasure.objects.create(code='BOX', name='صندوق', symbol='box')
        product = Product.objects.create(code='P002', name='منتج 2', unit_of_measure=unit)
        self.assertEqual(product.unit, 'صندوق')


class ProductCategoryHierarchyTest(TestCase):
    def test_hierarchical_category(self):
        parent = ProductCategory.objects.create(code='ELEC', name='إلكترونيات')
        child = ProductCategory.objects.create(code='COMP', name='حواسيب', parent=parent)
        self.assertEqual(str(child), 'إلكترونيات / حواسيب')
        self.assertEqual(child.get_full_code(), 'ELEC-COMP')
        self.assertFalse(parent.is_leaf)
        self.assertTrue(child.is_leaf)


class CatalogSettingsTest(TestCase):
    def test_singleton(self):
        s1 = CatalogSettings.get_settings()
        self.assertEqual(CatalogSettings.objects.count(), 1)
        # Trying to create a second instance should raise
        with self.assertRaises(ValueError):
            CatalogSettings.objects.create()

    def test_enforce_unit_validation(self):
        settings = CatalogSettings.get_settings()
        settings.enforce_unit = True
        settings.save()
        form = ProductForm(data={
            'code': 'P003', 'name': 'منتج بلا وحدة',
            'purchase_price': '10', 'selling_price': '20',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('يجب تحديد وحدة القياس', str(form.errors))

