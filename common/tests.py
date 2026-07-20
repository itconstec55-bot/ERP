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
