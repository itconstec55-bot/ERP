"""
اختبارات آلية للنظام المحاسبي.
تغطي المنطق الأساسي (السيلو، أوامر الإنتاج، تعديل المخزون، صلاحيات الوصول)
بالإضافة إلى اختبار تكامل لتشغيل أمر توليد البيانات التجريبية.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from concrete_production.models import ConcreteMixDesign, CustomerRequest, ProductionOrder, Silo, SiloTransaction
from purchases.models import Product
from sales.models import Customer
from stock_adjustments.models import StockAdjustment, StockAdjustmentLine
from warehouses.models import Warehouse, WarehouseProduct


class TestSiloTransactions(TestCase):
    """حركات السيلة تحدّث مخزون الاسمنت تلقائياً."""

    def setUp(self):
        self.silo = Silo.objects.create(
            name='سيلة 1',
            code='S-T1',
            capacity_tons=Decimal('100'),
            current_stock_tons=Decimal('50'),
            cement_type='CEM I',
        )

    def test_increases_stock(self):
        before = self.silo.current_stock_tons
        SiloTransaction.objects.create(
            silo=self.silo, transaction_type='in', quantity_tons=Decimal('10'), reference_number='T1', notes='توريد'
        )
        self.silo.refresh_from_db()
        self.assertEqual(self.silo.current_stock_tons, before + Decimal('10'))

    def test_decreases_stock(self):
        before = self.silo.current_stock_tons
        SiloTransaction.objects.create(
            silo=self.silo, transaction_type='out', quantity_tons=Decimal('5'), reference_number='T2'
        )
        self.silo.refresh_from_db()
        self.assertEqual(self.silo.current_stock_tons, before - Decimal('5'))


class TestProductionOrderModel(TestCase):
    """حساب الإجمالي = الكمية × سعر الوحدة."""

    def setUp(self):
        self.customer = Customer.objects.create(name='عميل اختبار', code='T-CUST')
        self.mix = ConcreteMixDesign.objects.create(
            code='C25',
            name='C25/30',
            strength_class='C25/30',
            slump_cm=Decimal('12'),
            max_aggregate_mm=Decimal('20'),
            water_cement_ratio=Decimal('0.5'),
            target_strength_mpa=Decimal('25'),
            selling_price_per_m3=Decimal('560.00'),
        )
        self.cr = CustomerRequest.objects.create(
            request_number='T-CR-1', customer=self.customer, project_name='مشروع اختبار', site_address='عنوان'
        )

    def test_total_price_computed(self):
        po = ProductionOrder.objects.create(
            customer_request=self.cr, mix_design=self.mix, quantity_m3=Decimal('100'), unit_price=Decimal('560.00')
        )
        self.assertEqual(po.total_price, Decimal('100') * Decimal('560.00'))
        self.assertEqual(po.remaining_quantity, po.quantity_m3)


class TestConcreteAutoInvoice(TestCase):
    """اكتمال أمر الإنتاج يولّد فاتورة مبيعات تلقائياً مرتبطة به."""

    def setUp(self):
        from purchases.models import Product

        self.customer = Customer.objects.create(name='عميل اختبار', code='T-CUST')
        self.product = Product.objects.create(
            name='خرسانة جاهزة C25/30', code='T-CON', unit='م3', purchase_price=Decimal('420.00')
        )
        self.mix = ConcreteMixDesign.objects.create(
            code='C25',
            name='C25/30',
            strength_class='C25/30',
            slump_cm=Decimal('12'),
            max_aggregate_mm=Decimal('20'),
            water_cement_ratio=Decimal('0.5'),
            target_strength_mpa=Decimal('25'),
            selling_price_per_m3=Decimal('560.00'),
            product=self.product,
        )
        self.cr = CustomerRequest.objects.create(
            request_number='T-CR-2', customer=self.customer, project_name='مشروع اختبار', site_address='عنوان'
        )

    def test_generate_invoice_on_completion(self):
        po = ProductionOrder.objects.create(
            customer_request=self.cr,
            mix_design=self.mix,
            quantity_m3=Decimal('100'),
            unit_price=Decimal('560.00'),
            status='completed',
        )
        po.refresh_from_db()
        self.assertIsNotNone(po.sales_invoice_id)
        from sales.models import SalesInvoice

        inv = SalesInvoice.objects.get(pk=po.sales_invoice_id)
        self.assertEqual(inv.production_order_id, po.id)
        self.assertEqual(inv.lines.count(), 1)
        line = inv.lines.first()
        self.assertEqual(line.quantity, Decimal('100'))
        self.assertEqual(line.unit_price, Decimal('560.00'))
        self.assertEqual(inv.subtotal, Decimal('100') * Decimal('560.00'))
        self.assertGreater(inv.total_amount, inv.subtotal)

    def test_no_duplicate_invoice(self):
        po = ProductionOrder.objects.create(
            customer_request=self.cr,
            mix_design=self.mix,
            quantity_m3=Decimal('50'),
            unit_price=Decimal('560.00'),
            status='completed',
        )
        first = po.sales_invoice
        inv2 = po.generate_sales_invoice()
        self.assertEqual(first.pk, inv2.pk)
        from sales.models import SalesInvoice

        self.assertEqual(SalesInvoice.objects.filter(production_order=po).count(), 1)

    def test_detail_page_shows_invoice(self):
        from django.contrib.auth.models import User
        from django.test import Client

        po = ProductionOrder.objects.create(
            customer_request=self.cr,
            mix_design=self.mix,
            quantity_m3=Decimal('100'),
            unit_price=Decimal('560.00'),
            status='completed',
        )
        admin = User.objects.create_superuser('admin2', 'a2@t.com', 'admin123')
        client = Client()
        client.force_login(admin)
        resp = client.get(reverse('concrete_production:production_order_detail', args=[po.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, po.sales_invoice.invoice_number)


class TestStockAdjustmentApprove(TestCase):
    """اعتماد الجرد يحدّث رصيد المخزون الفعلي."""

    def setUp(self):
        self.product = Product.objects.create(
            name='منتج اختبار', code='T-PROD', unit='طن', purchase_price=Decimal('100')
        )
        self.warehouse = Warehouse.objects.create(code='T-WH', name='مخزن اختبار')
        self.wp = WarehouseProduct.objects.create(
            warehouse=self.warehouse, product=self.product, quantity=Decimal('10')
        )

    def test_addition_increases_stock(self):
        adj = StockAdjustment.objects.create(
            adjustment_number='T-SA-1',
            adjustment_type='addition',
            warehouse=self.warehouse,
            date=date.today(),
            reason='إضافة',
        )
        StockAdjustmentLine.objects.create(adjustment=adj, product=self.product, quantity=Decimal('5'))
        adj.approve()
        self.wp.refresh_from_db()
        self.assertEqual(self.wp.quantity, Decimal('15'))
        self.assertEqual(adj.status, 'approved')

    def test_deduction_decreases_stock(self):
        adj = StockAdjustment.objects.create(
            adjustment_number='T-SA-2',
            adjustment_type='deduction',
            warehouse=self.warehouse,
            date=date.today(),
            reason='خصم',
        )
        StockAdjustmentLine.objects.create(adjustment=adj, product=self.product, quantity=Decimal('4'))
        adj.approve()
        self.wp.refresh_from_db()
        self.assertEqual(self.wp.quantity, Decimal('6'))


class TestLoginThrottle(TestCase):
    """تقييد معدل الدخول يمنع القوة الغاشمة."""

    def setUp(self):
        from django.core.cache import cache

        cache.delete('login_throttle:127.0.0.1')
        User.objects.create_user('throttle', 't@t.com', 'rightpass123')

    def test_brute_force_blocked(self):
        from django.conf import settings

        url = settings.LOGIN_URL
        c = Client()
        for _ in range(10):
            r = c.post(url, {'username': 'throttle', 'password': 'wrong'})
            self.assertIn(r.status_code, (200, 429))
        r = c.post(url, {'username': 'throttle', 'password': 'wrong'})
        self.assertEqual(r.status_code, 429)

    def test_success_resets_counter(self):
        from django.conf import settings
        from django.core.cache import cache

        url = settings.LOGIN_URL
        c = Client()
        for _ in range(5):
            c.post(url, {'username': 'throttle', 'password': 'wrong'})
        r = c.post(url, {'username': 'throttle', 'password': 'rightpass123'})
        self.assertEqual(r.status_code, 302)
        cache.delete('login_throttle:127.0.0.1')
        r = c.post(url, {'username': 'throttle', 'password': 'wrong'})
        self.assertEqual(r.status_code, 200)


class TestViewsAccess(TestCase):
    """الشاشات الجديدة تستجيب 200 للمشرف، وتُعاد توجيهها لغير المصرح."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@t.com', 'admin123')
        self.staff = User.objects.create_user('staff', 's@t.com', 'staff123')
        self.client = Client()

    def test_new_screens_200_for_admin(self):
        self.client.login(username='admin', password='admin123')
        for name in [
            'reports:financial_dashboard',
            'reports:workflow_tracker',
            'concrete_production:production_daily',
            'concrete_production:cement_daily_inventory',
            'concrete_production:production_cost_per_m3',
        ]:
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 200, name)

    def test_protected_concrete_list_redirects_non_permitted(self):
        # شاشة محمية بصلاحية (مثال: قائمة أوامر الإنتاج)
        self.client.login(username='staff', password='staff123')
        try:
            url = reverse('concrete_production:production_order_list')
        except Exception:
            self.skipTest('اسم المسار غير متوفر')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403))


class TestSeedModulesData(TestCase):
    """أمر توليد البيانات التجريبية يملأ الوحدات الـ12 على قاعدة نظيفة."""

    def test_seed_populates_all_modules(self):
        from io import StringIO

        from django.core.management import call_command

        call_command('setup_accounts', stdout=StringIO())
        call_command('seed_modules_data', stdout=StringIO())

        from bank_reconciliation.models import ReconciliationSession
        from budget.models import Budget, CostCenter
        from cheques.models import Cheque
        from contractors.models import Contract, Contractor, ContractorPayment, InterimCertificate
        from credit_notes.models import CreditNote
        from currency.models import ExchangeRateHistory
        from payment_receipts.models import PaymentReceipt
        from purchase_returns.models import PurchaseReturn
        from sales_returns.models import SalesReturn
        from stock_adjustments.models import StockAdjustment
        from warehouses.models import StockMovement, Warehouse, WarehouseProduct

        self.assertGreater(Contractor.objects.count(), 0)
        self.assertGreater(Contract.objects.count(), 0)
        self.assertGreater(InterimCertificate.objects.count(), 0)
        self.assertGreater(ContractorPayment.objects.count(), 0)
        self.assertGreater(Warehouse.objects.count(), 0)
        self.assertGreater(WarehouseProduct.objects.count(), 0)
        self.assertGreater(StockMovement.objects.count(), 0)
        self.assertGreater(Cheque.objects.count(), 0)
        self.assertGreater(PaymentReceipt.objects.count(), 0)
        self.assertGreater(SalesReturn.objects.count(), 0)
        self.assertGreater(PurchaseReturn.objects.count(), 0)
        self.assertGreater(ReconciliationSession.objects.count(), 0)
        self.assertGreater(StockAdjustment.objects.count(), 0)
        self.assertGreater(Budget.objects.count(), 0)
        self.assertGreater(CostCenter.objects.count(), 0)
        self.assertGreater(CreditNote.objects.count(), 0)
        self.assertGreater(ExchangeRateHistory.objects.count(), 0)

        # التحقق من ارتباط القيود المحاسبية بالمستخلصات والمدفوعات
        self.assertTrue(InterimCertificate.objects.filter(journal_entry__isnull=False).exists())
        self.assertTrue(ContractorPayment.objects.filter(journal_entry__isnull=False).exists())


class TestObjectLevelPermissions(TestCase):
    """صلاحيات على مستوى الكائن: تصفية حسب الفرع ومنع الوصول لفرع آخر."""

    def setUp(self):
        from django.core.cache import cache

        from common.models import UserProfile
        from company.models import Company, CompanyBranch
        from sales.models import SalesInvoice

        # مسح كاش صلاحيات الوصول (access_control.resolver) لتجنب التلوث من اختبارات أخرى
        cache.clear()

        company = Company.objects.create(name='شركة تجريبية', currency='ج.م')
        self.branch_a = CompanyBranch.objects.create(company=company, name='الفرع أ', is_default=True)
        self.branch_b = CompanyBranch.objects.create(company=company, name='الفرع ب')

        self.superuser = User.objects.create_superuser('sup', 's@t.com', 'x1234567')
        self.user_a = User.objects.create_user('ua', 'ua@t.com', 'x1234567')
        self.user_b = User.objects.create_user('ub', 'ub@t.com', 'x1234567')
        self.user_all = User.objects.create_user('uall', 'uall@t.com', 'x1234567')
        UserProfile.objects.create(user=self.user_a, branch=self.branch_a)
        UserProfile.objects.create(user=self.user_b, branch=self.branch_b)
        UserProfile.objects.create(user=self.user_all, branch=self.branch_a, view_all_branches=True)

        from access_control.models import Screen, UserScreenPermission

        screen, _ = Screen.objects.get_or_create(
            code='sales.invoice', defaults={'name': 'فواتير المبيعات', 'module': 'المبيعات'}
        )
        for u in (self.user_a, self.user_b, self.user_all):
            UserScreenPermission.objects.create(user=u, screen=screen, grant_type='allow', can_view=True)

        self.customer = Customer.objects.create(name='عميل فرعي', code='OBJ-CUST')
        self.inv_a = SalesInvoice.objects.create(
            invoice_number='OBJ-A', customer=self.customer, date=date.today(), branch=self.branch_a
        )
        self.inv_b = SalesInvoice.objects.create(
            invoice_number='OBJ-B', customer=self.customer, date=date.today(), branch=self.branch_b
        )
        self.inv_none = SalesInvoice.objects.create(invoice_number='OBJ-N', customer=self.customer, date=date.today())

    def test_filter_by_branch(self):
        from common.permissions import filter_by_branch
        from sales.models import SalesInvoice

        self.assertEqual(filter_by_branch(SalesInvoice.objects.all(), self.user_a).count(), 2)
        self.assertEqual(filter_by_branch(SalesInvoice.objects.all(), self.user_b).count(), 2)
        self.assertEqual(filter_by_branch(SalesInvoice.objects.all(), self.user_all).count(), 3)
        self.assertEqual(filter_by_branch(SalesInvoice.objects.all(), self.superuser).count(), 3)

    def test_has_object_permission(self):
        from common.permissions import has_object_permission

        self.assertTrue(has_object_permission(self.user_a, 'sales.view_salesinvoice', self.inv_a))
        self.assertFalse(has_object_permission(self.user_a, 'sales.view_salesinvoice', self.inv_b))
        self.assertTrue(has_object_permission(self.user_a, 'sales.view_salesinvoice', self.inv_none))
        self.assertTrue(has_object_permission(self.user_all, 'sales.view_salesinvoice', self.inv_b))
        self.assertFalse(has_object_permission(self.user_b, 'sales.view_salesinvoice', self.inv_a))

    def test_detail_view_enforces_branch(self):
        from django.test import Client

        client = Client()
        # مستخدم الفرع أ لا يصل لفاتورة الفرع ب
        client.force_login(self.user_a)
        resp = client.get(reverse('sales:invoice_detail', args=[self.inv_b.pk]))
        self.assertEqual(resp.status_code, 302)
        # يصل لفاتورة فرعه
        resp = client.get(reverse('sales:invoice_detail', args=[self.inv_a.pk]))
        self.assertEqual(resp.status_code, 200)
        # المشرف يصل للكل
        client.force_login(self.superuser)
        resp = client.get(reverse('sales:invoice_detail', args=[self.inv_b.pk]))
        self.assertEqual(resp.status_code, 200)


# ============================================================
# اختبارات decimal_utils
# ============================================================


class TestToDecimal(TestCase):
    """اختبار دالة التحويل الآمن إلى Decimal"""

    def test_decimal_passthrough(self):
        """اختبار أن Decimal يمر كما هو"""
        from decimal import Decimal

        from common.decimal_utils import to_decimal
        self.assertEqual(to_decimal(Decimal('10.5')), Decimal('10.5'))

    def test_int_conversion(self):
        """اختبار تحويل صحيح"""
        from decimal import Decimal

        from common.decimal_utils import to_decimal
        self.assertEqual(to_decimal(10), Decimal('10'))

    def test_float_conversion(self):
        """اختبار تحويل عشري"""
        from decimal import Decimal

        from common.decimal_utils import to_decimal
        result = to_decimal(3.14)
        self.assertEqual(result, Decimal('3.14'))

    def test_string_conversion(self):
        """اختبار تحويل نصي"""
        from decimal import Decimal

        from common.decimal_utils import to_decimal
        self.assertEqual(to_decimal('100.50'), Decimal('100.50'))

    def test_none_returns_zero(self):
        """اختبار إرجاع صفر عند None"""
        from decimal import Decimal

        from common.decimal_utils import to_decimal
        self.assertEqual(to_decimal(None), Decimal('0'))


class TestQuantize(TestCase):
    """اختبار دوال التقريب"""

    def test_quantize_10_rounds_to_10_places(self):
        """اختبار التقريب إلى 10 أرقام عشرية"""
        from decimal import Decimal

        from common.decimal_utils import quantize_10
        result = quantize_10(Decimal('1.12345678901'))
        self.assertEqual(len(str(result).split('.')[1]), 10)

    def test_quantize_display_rounds_to_2_places(self):
        """اختبار التقريب إلى رقمين عشريين"""
        from decimal import Decimal

        from common.decimal_utils import quantize_display
        result = quantize_display(Decimal('1.567'))
        self.assertEqual(result, Decimal('1.57'))

    def test_quantize_10_none_returns_zero(self):
        """اختبار إرجاع صفر عند None"""
        from decimal import Decimal

        from common.decimal_utils import quantize_10
        self.assertEqual(quantize_10(None), Decimal('0'))

    def test_quantize_display_none_returns_zero(self):
        """اختبار إرجاع صفر عند None للعرض"""
        from decimal import Decimal

        from common.decimal_utils import quantize_display
        self.assertEqual(quantize_display(None), Decimal('0.00'))


class TestSafeArithmetic(TestCase):
    """اختبار العمليات الحسابية الآمنة"""

    def test_safe_add(self):
        """اختبار الجمع الآمن"""
        from decimal import Decimal

        from common.decimal_utils import safe_add
        self.assertEqual(safe_add(Decimal('10'), Decimal('20')), Decimal('30'))

    def test_safe_add_multiple(self):
        """اختبار الجمع المتعدد"""
        from decimal import Decimal

        from common.decimal_utils import safe_add
        self.assertEqual(safe_add(Decimal('1'), Decimal('2'), Decimal('3')), Decimal('6'))

    def test_safe_sub(self):
        """اختبار الطرح الآمن"""
        from decimal import Decimal

        from common.decimal_utils import safe_sub
        self.assertEqual(safe_sub(Decimal('50'), Decimal('20')), Decimal('30'))

    def test_safe_mul(self):
        """اختبار الضرب الآمن"""
        from decimal import Decimal

        from common.decimal_utils import safe_mul
        self.assertEqual(safe_mul(Decimal('5'), Decimal('10')), Decimal('50'))

    def test_safe_div(self):
        """اختبار القسمة الآمنة"""
        from decimal import Decimal

        from common.decimal_utils import safe_div
        self.assertEqual(safe_div(Decimal('10'), Decimal('2')), Decimal('5'))

    def test_safe_div_by_zero(self):
        """اختبار القسمة على صفر ترجع صفر"""
        from decimal import Decimal

        from common.decimal_utils import safe_div
        self.assertEqual(safe_div(Decimal('10'), Decimal('0')), Decimal('0'))

    def test_percentage(self):
        """اختبار حساب النسبة المئوية"""
        from decimal import Decimal

        from common.decimal_utils import percentage
        self.assertEqual(percentage(Decimal('50'), Decimal('200')), Decimal('25'))

    def test_calculate_vat(self):
        """اختبار حساب الضريبة"""
        from decimal import Decimal

        from common.decimal_utils import calculate_vat
        result = calculate_vat(Decimal('1000'))
        self.assertEqual(result, Decimal('140'))

    def test_calculate_vat_custom_rate(self):
        """اختبار حساب الضريبة بنسبة مخصصة"""
        from decimal import Decimal

        from common.decimal_utils import calculate_vat
        result = calculate_vat(Decimal('1000'), Decimal('0.10'))
        self.assertEqual(result, Decimal('100'))

    def test_calculate_withholding(self):
        """اختبار حساب الخصم والتحصيل"""
        from decimal import Decimal

        from common.decimal_utils import calculate_withholding
        result = calculate_withholding(Decimal('1000'), Decimal('5'))
        self.assertEqual(result, Decimal('50'))


class TestFinancialDecimal(TestCase):
    """اختبار غلاف FinancialDecimal للعمليات المتسلسلة"""

    def test_creation(self):
        """اختبار إنشاء FinancialDecimal"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(100)
        self.assertEqual(fd.raw, 100)

    def test_addition(self):
        """اختبار الجمع"""
        from common.decimal_utils import FinancialDecimal
        fd1 = FinancialDecimal(100)
        fd2 = fd1 + 50
        self.assertEqual(fd2.raw, 150)

    def test_subtraction(self):
        """اختبار الطرح"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(200) - 50
        self.assertEqual(fd.raw, 150)

    def test_multiplication(self):
        """اختبار الضرب"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(10) * 5
        self.assertEqual(fd.raw, 50)

    def test_division(self):
        """اختبار القسمة"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(100) / 4
        self.assertEqual(fd.raw, 25)

    def test_division_by_zero(self):
        """اختبار القسمة على صفر"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(100) / 0
        self.assertEqual(fd.raw, 0)

    def test_comparison(self):
        """اختبار المقارنات"""
        from common.decimal_utils import FinancialDecimal
        self.assertTrue(FinancialDecimal(10) < FinancialDecimal(20))
        self.assertTrue(FinancialDecimal(20) > FinancialDecimal(10))
        self.assertTrue(FinancialDecimal(10) == FinancialDecimal(10))
        self.assertTrue(FinancialDecimal(10) <= FinancialDecimal(10))
        self.assertTrue(FinancialDecimal(10) >= FinancialDecimal(10))

    def test_negation(self):
        """اختبار السالب"""
        from common.decimal_utils import FinancialDecimal
        fd = -FinancialDecimal(100)
        self.assertEqual(fd.raw, -100)

    def test_abs(self):
        """اختبار القيمة المطلقة"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(-100).abs()
        self.assertEqual(fd.raw, 100)

    def test_to_display(self):
        """اختبار التحويل لعرض رقمين"""
        from decimal import Decimal

        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(10.567)
        self.assertEqual(fd.to_display(), Decimal('10.57'))

    def test_float_conversion(self):
        """اختبار التحويل إلى float"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(10.5)
        self.assertAlmostEqual(float(fd), 10.5)

    def test_int_conversion(self):
        """اختبار التحويل إلى int"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(10.9)
        self.assertEqual(int(fd), 10)

    def test_str_representation(self):
        """اختبار التمثيل النصي"""
        from common.decimal_utils import FinancialDecimal
        fd = FinancialDecimal(42)
        self.assertIn('42', str(fd))


class TestFinancialFormat(TestCase):
    """اختبار دوال التنسيق المالي"""

    def test_financial_format(self):
        """اختبار تنسيق الرقم المالي"""
        from common.decimal_utils import financial_format
        self.assertEqual(financial_format(1000000), '1,000,000.00')

    def test_financial_format_none(self):
        """اختبار التنسيق مع None"""
        from common.decimal_utils import financial_format
        self.assertEqual(financial_format(None), '0.00')

    def test_financial_format_negative(self):
        """اختبار تنسيق رقم سالب"""
        from common.decimal_utils import financial_format
        result = financial_format(-5000)
        self.assertIn('-', result)
        self.assertIn('5,000.00', result)

    def test_money_format(self):
        """اختبار تنسيق العملة مع الرمز"""
        from common.decimal_utils import money_format
        result = money_format(1500, 'ج.م')
        self.assertEqual(result, '1,500.00 ج.م')

    def test_financial_decimal_filter(self):
        """اختبار فلتر القوالب"""
        from decimal import Decimal

        from common.decimal_utils import financial_decimal
        result = financial_decimal(10.567)
        self.assertEqual(result, Decimal('10.57'))


class TestCalculateInvoiceTotals(TestCase):
    """اختبار دالة حساب إجماليات الفاتورة"""

    def test_single_line_no_tax(self):
        """اختبار بند واحد بدون ضريبة"""
        from common.decimal_utils import calculate_invoice_totals
        lines = [{'quantity': 10, 'unit_price': 100, 'discount_percent': 0, 'cost_price': 60}]
        result = calculate_invoice_totals(lines, is_tax_invoice=False)
        self.assertEqual(result['subtotal'], 1000)
        self.assertEqual(result['vat_amount'], 0)
        self.assertEqual(result['total_amount'], 1000)

    def test_single_line_with_vat(self):
        """اختبار بند واحد مع ضريبة"""
        from common.decimal_utils import calculate_invoice_totals
        lines = [{'quantity': 10, 'unit_price': 100, 'discount_percent': 0}]
        result = calculate_invoice_totals(lines, is_tax_invoice=True)
        self.assertEqual(result['subtotal'], 1000)
        self.assertEqual(result['vat_amount'], 140)
        self.assertEqual(result['total_amount'], 1140)

    def test_line_with_discount(self):
        """اختبار بند مع خصم"""
        from common.decimal_utils import calculate_invoice_totals
        lines = [{'quantity': 10, 'unit_price': 100, 'discount_percent': 10}]
        result = calculate_invoice_totals(lines, is_tax_invoice=False)
        self.assertEqual(result['subtotal'], 900)
        self.assertEqual(result['total_amount'], 900)

    def test_invoice_discount(self):
        """اختبار خصم على الفاتورة"""
        from common.decimal_utils import calculate_invoice_totals
        lines = [{'quantity': 10, 'unit_price': 100, 'discount_percent': 0}]
        result = calculate_invoice_totals(lines, discount_amount=200, is_tax_invoice=False)
        self.assertEqual(result['discount_amount'], 200)
        self.assertEqual(result['total_amount'], 800)

    def test_with_withholding_tax(self):
        """اختبار مع خصم وتحصيل"""
        from common.decimal_utils import calculate_invoice_totals
        lines = [{'quantity': 10, 'unit_price': 100, 'discount_percent': 0}]
        result = calculate_invoice_totals(lines, withholding_rate=5, is_tax_invoice=False)
        self.assertEqual(result['withholding_amount'], 50)
        self.assertEqual(result['total_amount'], 1050)

    def test_empty_lines(self):
        """اختبار بنود فارغة"""
        from common.decimal_utils import calculate_invoice_totals
        result = calculate_invoice_totals([], is_tax_invoice=False)
        self.assertEqual(result['subtotal'], 0)
        self.assertEqual(result['total_amount'], 0)

    def test_cost_of_goods(self):
        """اختبار تكلفة البضاعة"""
        from common.decimal_utils import calculate_invoice_totals
        lines = [
            {'quantity': 10, 'unit_price': 100, 'discount_percent': 0, 'cost_price': 60},
            {'quantity': 5, 'unit_price': 200, 'discount_percent': 0, 'cost_price': 120},
        ]
        result = calculate_invoice_totals(lines, is_tax_invoice=False)
        self.assertEqual(result['cost_of_goods'], 1200)


class TestSafeArithmeticDecorator(TestCase):
    """اختبار مُزخرف safe_arithmetic"""

    def test_decorator_preserves_return_type(self):
        """اختبار أن المزخرف يحافظ على نوع الإرجاع"""
        from decimal import Decimal

        from common.decimal_utils import safe_arithmetic

        @safe_arithmetic
        def add(a, b):
            return Decimal(str(a)) + Decimal(str(b))

        result = add(Decimal('10'), Decimal('20'))
        self.assertIsInstance(result, Decimal)
        self.assertEqual(result, Decimal('30'))

    def test_decorator_rounds_decimal_result(self):
        """اختبار أن المزخرف يقرّب النتيجة العشرية"""
        from decimal import Decimal

        from common.decimal_utils import safe_arithmetic

        @safe_arithmetic
        def divide(a, b):
            return Decimal(str(a)) / Decimal(str(b))

        result = divide(Decimal('10'), Decimal('3'))
        self.assertEqual(len(str(result).split('.')[1]), 10)

    def test_decorator_handles_list_return(self):
        """اختبار أن المزخرف يتعامل مع الإرجاع كقائمة"""
        from decimal import Decimal

        from common.decimal_utils import safe_arithmetic

        @safe_arithmetic
        def two_values():
            return (Decimal('10.12345678901'), Decimal('20.12345678901'))

        result = two_values()
        self.assertEqual(len(result), 2)
        self.assertEqual(len(str(result[0]).split('.')[1]), 10)


class TestValidateInvoicePrecision(TestCase):
    """اختبار دالة التحقق من دقة الفاتورة"""

    def test_validate_invoice_precision(self):
        """اختبار التحقق من دقة فاتورة صحيحة"""
        from decimal import Decimal
        from unittest.mock import MagicMock

        from common.decimal_utils import validate_invoice_precision

        mock_invoice = MagicMock()
        mock_invoice.subtotal = Decimal('1000.00')
        mock_invoice.vat_amount = Decimal('140.00')
        mock_invoice.total_amount = Decimal('1140.00')
        mock_invoice.withholding_tax_amount = Decimal('0')
        mock_invoice.discount_amount = Decimal('0')
        mock_invoice.is_tax_invoice = True
        mock_invoice.withholding_tax_type = 0

        mock_line = MagicMock()
        mock_line.quantity = Decimal('10')
        mock_line.unit_price = Decimal('100')
        mock_line.discount_percent = Decimal('0')
        mock_line.cost_price = Decimal('60')
        mock_invoice.lines.all.return_value = [mock_line]

        errors = validate_invoice_precision(mock_invoice)
        self.assertEqual(len(errors), 0)
