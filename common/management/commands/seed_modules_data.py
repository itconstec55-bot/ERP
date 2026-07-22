"""أمر توليد بيانات تجريبية شاملة للوحدات الـ12 المفقودة.

يُنفَّذ بعد setup_accounts و seed_dummy_data. آمن للإعادة (يتخطى أي قسم له بيانات).
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'توليد بيانات تجريبية للوحدات المفقودة: السيلو، الخرسانة، المقاولين، المخازن، الشيكات، السندات، المرتجعات، التسوية، الجرد، الموازنة، الإشعارات، العملات'

    def handle(self, *args, **opts):
        self.admin = self.get_admin()
        self.today = date(2026, 7, 13)
        random.seed(2026)

        self.make_banks_safes()
        self.make_customers_products()
        self.make_products_for_concrete()
        self.make_currencies()
        self.make_warehouses()
        self.make_concrete_production()
        self.make_contractors()
        self.make_cheques()
        self.make_payment_receipts()
        self.make_sales_returns()
        self.make_purchase_returns()
        self.make_bank_reconciliation()
        self.make_stock_adjustments()
        self.make_budget()
        self.make_credit_notes()
        self.make_currency_rates()

        self.stdout.write(self.style.SUCCESS('\n✅ تم توليد البيانات التجريبية بنجاح.'))

    # ───────────────────────────────── helpers ─────────────────────────────────
    def get_admin(self):
        from django.contrib.auth.models import User

        return User.objects.filter(is_superuser=True).first()

    def acct(self, code):
        from accounts.models import Account

        return Account.objects.filter(code=code).first()

    def d(self, label, fn):
        try:
            fn()
            self.stdout.write(f'  • {label}: تم')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  • {label}: خطأ - {e}'))

    # ───────────────────────────────── banks/safes ─────────────────────────────────
    def make_banks_safes(self):
        from treasury.models import Bank, Safe

        def run():
            if Bank.objects.exists() or Safe.objects.exists():
                return
            cash = self.acct('1500')
            bank_acc = self.acct('1600')
            b1 = Bank.objects.create(
                name='البنك الأهلي المصري',
                branch='فرع وسط البلد',
                account_number='1001123456',
                iban='EG123456',
                swift_code='NBEGEGCX',
                account=bank_acc,
                current_balance=Decimal('850000.00'),
            )
            b2 = Bank.objects.create(
                name='بنك CIB',
                branch='فرع التجمع',
                account_number='2002987654',
                iban='EG654321',
                swift_code='CIBEEGCX',
                account=bank_acc,
                current_balance=Decimal('430000.00'),
            )
            Safe.objects.create(
                name='خزينة الإدارة',
                responsible_person='أحمد محاسب',
                account=cash,
                current_balance=Decimal('120000.00'),
                maximum_limit=Decimal('500000.00'),
            )
            Safe.objects.create(
                name='خزينة الموقع',
                responsible_person='محمود أمين',
                account=cash,
                current_balance=Decimal('60000.00'),
                maximum_limit=Decimal('300000.00'),
            )

        self.d('البنوك والخزائن', run)

    # ───────────────────────────────── customers/products ─────────────────────────────────
    def make_customers_products(self):
        from purchases.models import Product, Supplier
        from sales.models import Customer

        def run():
            cust_acc = self.acct('1100')
            supp_acc = self.acct('3100')
            if Customer.objects.count() < 6:
                names = [
                    'شركة الأفق للمقاولات',
                    'مؤسسة البناء الحديث',
                    'مجموعة النيل العقارية',
                    'شركة الرواد للتطوير',
                    'مصنع الخرسانة الجاهزة',
                    'مشروع برج النيل',
                ]
                for i, n in enumerate(names, 1):
                    Customer.objects.get_or_create(
                        name=n,
                        defaults={
                            'code': f'C-2026-{i:03d}',
                            'account': cust_acc,
                            'phone': f'01{random.randint(100000000, 999999999)}',
                        },
                    )
            if Supplier.objects.count() < 6:
                names = [
                    'شركة أسمنت العامرية',
                    'مصانع الرمل والركام',
                    'شركة كيماويات البناء',
                    'مؤسسة نقل المواد',
                    'شركة الحديد والصلب',
                    'مورد المضخات',
                ]
                for i, n in enumerate(names, 1):
                    Supplier.objects.get_or_create(
                        name=n,
                        defaults={
                            'code': f'S-2026-{i:03d}',
                            'account': supp_acc,
                            'phone': f'01{random.randint(100000000, 999999999)}',
                        },
                    )
            if Product.objects.filter(name__icontains='خرسانة').count() == 0:
                Product.objects.get_or_create(
                    name='خرسانة جاهزة C25/30',
                    defaults={
                        'code': 'CON-C25',
                        'unit': 'م3',
                        'purchase_price': Decimal('420.00'),
                        'selling_price': Decimal('560.00'),
                    },
                )
                Product.objects.get_or_create(
                    name='خرسانة جاهزة C30/37',
                    defaults={
                        'code': 'CON-C30',
                        'unit': 'م3',
                        'purchase_price': Decimal('450.00'),
                        'selling_price': Decimal('600.00'),
                    },
                )

        self.d('العملاء والموردون والمنتجات', run)

    def make_products_for_concrete(self):
        from purchases.models import Product

        def run():
            base = [
                ('أسمنت بورتلاندي OPC', 'CEM-OPC', 'طن', Decimal('1100.00'), Decimal('1300.00')),
                ('أسمنت مقاوم SRC', 'CEM-SRC', 'طن', Decimal('1200.00'), Decimal('1400.00')),
                ('رمل ناعم', 'AGG-SAND', 'م3', Decimal('60.00'), Decimal('80.00')),
                ('ركام خشن 10-20', 'AGG-1020', 'م3', Decimal('70.00'), Decimal('90.00')),
                ('ركام خشن 5-10', 'AGG-0510', 'م3', Decimal('70.00'), Decimal('90.00')),
                ('مادة كيميائية SP', 'ADM-SP', 'طن', Decimal('5000.00'), Decimal('6000.00')),
                ('مياه خلط', 'WATER', 'م3', Decimal('5.00'), Decimal('5.00')),
            ]
            for name, code, unit, pp, up in base:
                Product.objects.get_or_create(
                    name=name, defaults={'code': code, 'unit': unit, 'purchase_price': pp, 'selling_price': up}
                )

        self.d('منتجات الخرسانة (أسمنت/ركام/إضافات)', run)

    # ───────────────────────────────── currencies ─────────────────────────────────
    def make_currencies(self):
        from currency.models import Currency

        def run():
            if Currency.objects.count() == 0:
                base = [
                    ('EGP', 'جنيه مصري', 'ج.م', Decimal('1'), True),
                    ('USD', 'دولار أمريكي', '$', Decimal('48.50'), False),
                    ('EUR', 'يورو', '€', Decimal('52.30'), False),
                    ('SAR', 'ريال سعودي', 'ر.س', Decimal('12.90'), False),
                    ('GBP', 'جنيه إسترليني', '£', Decimal('61.00'), False),
                ]
                for code, name, sym, rate, is_base in base:
                    Currency.objects.create(
                        code=code, name=name, symbol=sym, exchange_rate_to_egp=rate, is_base=is_base
                    )

        self.d('العملات', run)

    # ───────────────────────────────── warehouses ─────────────────────────────────
    def make_warehouses(self):
        from purchases.models import Product
        from warehouses.models import StockMovement, Warehouse, WarehouseProduct

        def run():
            if Warehouse.objects.count() == 0:
                Warehouse.objects.create(
                    code='WH-01', name='مخزن المواد الخام', location='المصنع الرئيسي', manager='سعيد'
                )
                Warehouse.objects.create(code='WH-02', name='مخزن قطع الغيار', location='ورشة الصيانة', manager='وليد')
                Warehouse.objects.create(code='WH-03', name='مخزن المنتجات النهائية', location='الموقع', manager='طارق')
            if WarehouseProduct.objects.count() == 0:
                products = Product.objects.all()
                for wh in Warehouse.objects.all()[:3]:
                    for p in products[:6]:
                        wp = WarehouseProduct.objects.create(
                            warehouse=wh,
                            product=p,
                            quantity=Decimal(random.randint(20, 400)),
                            minimum_quantity=Decimal('10'),
                            maximum_quantity=Decimal('1000'),
                        )
                        StockMovement.objects.create(
                            movement_number=f'MV-{wh.code}-{p.code}-{random.randint(1000, 9999)}',
                            movement_type='in',
                            warehouse=wh,
                            product=p,
                            quantity=wp.quantity,
                            unit_cost=wp.quantity * p.purchase_price,
                            date=self.today - timedelta(days=random.randint(10, 60)),
                            performed_by=self.admin,
                        )

        self.d('المخازن وأرصدة البداية والحركات', run)

    # ───────────────────────────────── concrete production ─────────────────────────────────
    def make_concrete_production(self):
        from concrete_production.models import (
            ConcreteMixDesign,
            CustomerRequest,
            DeliverySchedule,
            MixComponent,
            ProductionBatch,
            ProductionCost,
            ProductionOrder,
            Silo,
            SiloTransaction,
            Truck,
        )
        from purchases.models import Product
        from sales.models import Customer

        def run():
            if CustomerRequest.objects.exists():
                return
            # تصاميم الخلطات
            if ConcreteMixDesign.objects.count() == 0:
                designs = [
                    ('C25/30', 'C25/30', 'C25/30', Decimal('12.0'), Decimal('20'), Decimal('0.50'), Decimal('25')),
                    ('C30/37', 'C30/37', 'C30/37', Decimal('10.0'), Decimal('20'), Decimal('0.45'), Decimal('30')),
                    ('C35/45', 'C35/45', 'C35/45', Decimal('8.0'), Decimal('16'), Decimal('0.42'), Decimal('35')),
                ]
                product_map = {'C25/30': 'CON-C25', 'C30/37': 'CON-C30', 'C35/45': 'CON-C30'}
                for code, name, sc, slump, agg, wcr, ts in designs:
                    md = ConcreteMixDesign.objects.create(
                        code=code,
                        name=name,
                        strength_class=sc,
                        slump_cm=slump,
                        max_aggregate_mm=agg,
                        water_cement_ratio=wcr,
                        target_strength_mpa=ts,
                        selling_price_per_m3=Decimal('560.00'),
                        product=Product.objects.filter(code=product_map.get(code)).first(),
                    )
                    comps = [
                        ('cement', 'أسمنت OPC', Product.objects.get(code='CEM-OPC'), Decimal('320')),
                        ('fine_aggregate', 'رمل', Product.objects.get(code='AGG-SAND'), Decimal('620')),
                        ('coarse_aggregate', 'ركام 10-20', Product.objects.get(code='AGG-1020'), Decimal('900')),
                        ('water', 'مياه', Product.objects.get(code='WATER'), Decimal('160')),
                        ('ad_additive', 'مضافة SP', Product.objects.get(code='ADM-SP'), Decimal('4')),
                    ]
                    for i, (ct, nm, prod, qty) in enumerate(comps, 1):
                        MixComponent.objects.create(
                            mix_design=md, component_type=ct, name=nm, quantity_kg=qty, product=prod, order=i
                        )
                    md.calculate_cost()

            # أسطول الشاحنات
            if Truck.objects.count() == 0:
                for i, plate in enumerate(['ط ا ب 1234', 'ط ا ب 5678', 'ط ج د 9012', 'ط و ز 3456'], 1):
                    Truck.objects.create(
                        plate_number=plate,
                        driver_name=f'سائق {i}',
                        driver_phone=f'01{random.randint(100000000, 999999999)}',
                        capacity_m3=random.choice([8, 9, 10]),
                        status='available',
                    )

            trucks = list(Truck.objects.all())
            customers = list(Customer.objects.all())
            designs = list(ConcreteMixDesign.objects.all())
            silos = list(Silo.objects.all())

            # فرع افتراضي لعرض الصلاحيات على مستوى الكائن
            from company.models import Company, CompanyBranch

            branch = None
            if CompanyBranch.objects.count() == 0 and Company.objects.exists():
                branch = CompanyBranch.objects.create(
                    company=Company.objects.first(), name='الفرع الرئيسي', is_default=True, is_active=True
                )

            statuses_cr = ['new', 'confirmed', 'in_production', 'delivered']
            statuses_po = ['draft', 'scheduled', 'in_progress', 'completed']
            for i in range(1, 9):
                cr = CustomerRequest.objects.create(
                    request_number=f'CR-2026-{i:04d}',
                    customer=random.choice(customers),
                    project_name=f'مشروع عمارة سكنية {i}',
                    site_address=f'شارع {i}، الحي {i % 5 + 1}',
                    contact_person=f'مهندس {i}',
                    contact_phone=f'01{random.randint(100000000, 999999999)}',
                    status=random.choice(statuses_cr),
                    created_by=self.admin,
                )
                md = random.choice(designs)
                po = ProductionOrder.objects.create(
                    customer_request=cr,
                    mix_design=md,
                    quantity_m3=Decimal(random.randint(40, 300)),
                    priority=random.choice(['normal', 'urgent', 'very_urgent']),
                    status=random.choice(statuses_po),
                    scheduled_date=self.today - timedelta(days=random.randint(0, 30)),
                    unit_price=md.selling_price_per_m3,
                    created_by=self.admin,
                    branch=branch if i % 2 == 0 else None,
                )
                # دفعة + تسليم
                if po.status in ['in_progress', 'completed']:
                    for j in range(1, random.randint(2, 4)):
                        batch = ProductionBatch.objects.create(
                            production_order=po,
                            truck=random.choice(trucks),
                            quantity_m3=Decimal(random.randint(6, 10)),
                            actual_quantity_m3=Decimal(random.randint(6, 10)),
                            status='completed',
                            mixing_time=timezone.now() - timedelta(days=j),
                            departure_time=timezone.now() - timedelta(days=j, hours=1),
                            arrival_time=timezone.now() - timedelta(days=j, hours=2),
                            pouring_end=timezone.now() - timedelta(days=j, hours=3),
                        )
                        DeliverySchedule.objects.create(
                            production_order=po,
                            batch=batch,
                            delivery_date=self.today - timedelta(days=j),
                            time_slot_from=timezone.now().time(),
                            time_slot_to=timezone.now().time(),
                            truck=batch.truck,
                            status='delivered',
                            sequence=j,
                        )
                        # استهلاك من السيلو
                        if silos:
                            silo = random.choice(silos)
                            SiloTransaction.objects.create(
                                silo=silo,
                                transaction_type='out',
                                quantity_tons=Decimal(batch.quantity_m3 * Decimal('0.32')),
                                reference_number=batch.batch_number,
                                production_order=po,
                                created_by=self.admin,
                            )
                    # تكاليف
                    for ctype in ['materials', 'labor', 'transport', 'fuel']:
                        ProductionCost.objects.create(
                            production_order=po,
                            cost_type=ctype,
                            amount=Decimal(random.randint(500, 5000)),
                            description=f'تكلفة {ctype}',
                            date=self.today - timedelta(days=random.randint(0, 20)),
                        )

        self.d('إنتاج الخرسانة (طلبات/أوامر/دفعات/شاحنات/تكاليف/حركات سيلو)', run)

    # ───────────────────────────────── contractors ─────────────────────────────────
    def make_contractors(self):
        from contractors.models import (
            CertificateItem,
            Contract,
            ContractItem,
            Contractor,
            ContractorPayment,
            InterimCertificate,
        )

        def run():
            if Contractor.objects.exists():
                return
            if Contractor.objects.count() == 0:
                contractor_data = [
                    ('شركة البناء المتطور', 'company', 'أعمال خرسانية', Decimal('500000')),
                    ('مؤسسة الطرق الحديثة', 'company', 'رصف طرق', Decimal('300000')),
                    ('مكتب الإنشاءات الهندسية', 'individual', 'أعمال معمارية', Decimal('200000')),
                    ('شركة المقاولات الكبرى', 'company', 'مقاولات عامة', Decimal('800000')),
                ]
                suppliers_acc = self.acct('3100')
                for i, (name, ctype, spec, cl) in enumerate(contractor_data, 1):
                    Contractor.objects.create(
                        code=f'CONT-2026-{i:03d}',
                        name=name,
                        contractor_type=ctype,
                        tax_number=f'2{random.randint(100000000, 999999999)}',
                        phone=f'01{random.randint(100000000, 999999999)}',
                        email=f'contractor{i}@example.com',
                        address=f'عنوان {i}',
                        speciality=spec,
                        credit_limit=cl,
                        retention_rate=Decimal('5'),
                        account=suppliers_acc,
                    )

            contractors = list(Contractor.objects.all())
            cost_acc = self.acct('5100')
            for idx, cont in enumerate(contractors, 1):
                if cont.contracts.exists():
                    continue
                contract = Contract.objects.create(
                    contractor=cont,
                    title=f'عقد أعمال {cont.name}',
                    contract_type='lump_sum',
                    status='active',
                    contract_amount=Decimal(random.randint(200000, 1500000)),
                    vat_rate=Decimal('14'),
                    signing_date=self.today - timedelta(days=120),
                    start_date=self.today - timedelta(days=100),
                    end_date=self.today + timedelta(days=200),
                    retention_rate=Decimal('5'),
                    advance_payment_percent=Decimal('10'),
                    cost_account=cost_acc,
                    created_by=self.admin,
                )
                contract.advance_payment_amount = contract.contract_amount * Decimal('0.10')
                contract.save()
                items_data = [
                    ('بند 1 - حفر', 'م3', Decimal('500'), Decimal('120')),
                    ('بند 2 - خرسانة', 'م3', Decimal('800'), Decimal('560')),
                    ('بند 3 - تشطيب', 'م2', Decimal('1200'), Decimal('300')),
                ]
                items = []
                for j, (desc, unit, qty, price) in enumerate(items_data, 1):
                    ci = ContractItem.objects.create(
                        contract=contract,
                        item_number=f'IT-{j}',
                        description=desc,
                        unit=unit,
                        quantity=qty,
                        unit_price=price,
                        order=j,
                    )
                    ci.executed_quantity = qty * Decimal('0.4')
                    ci.save()
                    items.append(ci)
                # مستخلصات
                prev = Decimal('0')
                for k in range(1, 4):
                    cert = InterimCertificate.objects.create(
                        contract=contract,
                        period_number=k,
                        status='paid',
                        period_from=self.today - timedelta(days=30 * k),
                        period_to=self.today - timedelta(days=30 * (k - 1)),
                        submission_date=self.today - timedelta(days=30 * (k - 1) + 2),
                        approval_date=self.today - timedelta(days=30 * (k - 1) + 5),
                        payment_date=self.today - timedelta(days=30 * (k - 1) + 10),
                        created_by=self.admin,
                    )
                    for ci in items:
                        portion = (ci.executed_quantity * Decimal(k)) / Decimal('3')
                        prev_portion = (ci.executed_quantity * Decimal(k - 1)) / Decimal('3')
                        CertificateItem.objects.create(
                            certificate=cert,
                            contract_item=ci,
                            previous_quantity=prev_portion,
                            current_quantity=portion - prev_portion,
                        )
                    cert.previous_amount = prev
                    cert.current_amount = sum(ci.amount for ci in cert.items.all())
                    cert.calculate_totals()
                    cert.create_journal_entry()
                    prev = cert.gross_amount
                    # دفعة ربطتها بالمستخلص
                    ContractorPayment.objects.create(
                        contract=contract,
                        certificate=cert,
                        amount=cert.net_amount * Decimal('0.9'),
                        payment_method='bank_transfer',
                        payment_date=cert.payment_date,
                        status='paid',
                        created_by=self.admin,
                    ).create_journal_entry()
                contract.calculate_totals()

        self.d('المقاولون (عقود/بنود/مستخلصات/مدفوعات)', run)

    # ───────────────────────────────── cheques ─────────────────────────────────
    def make_cheques(self):
        from cheques.models import Cheque
        from purchases.models import Supplier
        from sales.models import Customer

        def run():
            if Cheque.objects.exists():
                return
            customers = list(Customer.objects.all())
            suppliers = list(Supplier.objects.all())
            for i in range(1, 7):
                Cheque.objects.create(
                    cheque_number=f'CHK-R-{i:05d}',
                    cheque_type='received',
                    bank_name=random.choice(['البنك الأهلي', 'CIB', 'بنك مصر']),
                    amount=Decimal(random.randint(5000, 80000)),
                    currency='EGP',
                    issue_date=self.today - timedelta(days=random.randint(1, 20)),
                    due_date=self.today + timedelta(days=random.randint(5, 40)),
                    payee_name=customers[i % len(customers)].name if customers else 'عميل',
                    customer=random.choice(customers) if customers else None,
                    status=random.choice(['pending', 'deposited', 'cleared']),
                    created_by=self.admin,
                )
            for i in range(1, 7):
                Cheque.objects.create(
                    cheque_number=f'CHK-I-{i:05d}',
                    cheque_type='issued',
                    bank_name=random.choice(['البنك الأهلي', 'CIB', 'بنك مصر']),
                    amount=Decimal(random.randint(5000, 60000)),
                    currency='EGP',
                    issue_date=self.today - timedelta(days=random.randint(1, 20)),
                    due_date=self.today + timedelta(days=random.randint(5, 40)),
                    payee_name=suppliers[i % len(suppliers)].name if suppliers else 'مورد',
                    supplier=random.choice(suppliers) if suppliers else None,
                    status=random.choice(['pending', 'cleared']),
                    created_by=self.admin,
                )

        self.d('الشيكات (واردة/صادرة)', run)

    # ───────────────────────────────── payment receipts ─────────────────────────────────
    def make_payment_receipts(self):
        from payment_receipts.models import PaymentReceipt
        from purchases.models import Supplier
        from sales.models import Customer
        from treasury.models import Bank, Safe

        def run():
            if PaymentReceipt.objects.exists():
                return
            banks = list(Bank.objects.all())
            safes = list(Safe.objects.all())
            customers = list(Customer.objects.all())
            suppliers = list(Supplier.objects.all())
            for i in range(1, 8):
                cust = random.choice(customers) if customers else None
                pr = PaymentReceipt.objects.create(
                    receipt_number=f'PR-REC-{i:05d}',
                    receipt_type='receipt',
                    date=self.today - timedelta(days=random.randint(1, 30)),
                    amount=Decimal(random.randint(5000, 90000)),
                    payment_method=random.choice(['cash', 'bank_transfer', 'cheque']),
                    customer=cust,
                    bank=random.choice(banks) if banks else None,
                    safe=random.choice(safes) if safes else None,
                    cheque_number=f'CHK-R-{i:05d}' if random.random() > 0.5 else None,
                    description=f'تحصيل من {cust.name if cust else "عميل"}',
                    created_by=self.admin,
                )
                pr.create_journal_entry()
            for i in range(1, 8):
                supp = random.choice(suppliers) if suppliers else None
                pr = PaymentReceipt.objects.create(
                    receipt_number=f'PR-PAY-{i:05d}',
                    receipt_type='payment',
                    date=self.today - timedelta(days=random.randint(1, 30)),
                    amount=Decimal(random.randint(4000, 70000)),
                    payment_method=random.choice(['cash', 'bank_transfer', 'cheque']),
                    supplier=supp,
                    bank=random.choice(banks) if banks else None,
                    safe=random.choice(safes) if safes else None,
                    cheque_number=f'CHK-I-{i:05d}' if random.random() > 0.5 else None,
                    description=f'دفع إلى {supp.name if supp else "مورد"}',
                    created_by=self.admin,
                )
                pr.create_journal_entry()

        self.d('سندات القبض والدفع', run)

    # ───────────────────────────────── sales returns ─────────────────────────────────
    def make_sales_returns(self):
        from purchases.models import Product
        from sales.models import Customer, SalesInvoice
        from sales_returns.models import SalesReturn, SalesReturnLine

        def run():
            if SalesReturn.objects.exists():
                return
            customers = list(Customer.objects.all())
            products = list(Product.objects.all())
            invoices = list(SalesInvoice.objects.all())
            for i in range(1, 6):
                cust = random.choice(customers) if customers else None
                inv = random.choice(invoices) if invoices else None
                sr = SalesReturn.objects.create(
                    return_number=f'SR-2026-{i:04d}',
                    date=self.today - timedelta(days=random.randint(1, 25)),
                    customer=cust,
                    original_invoice=inv,
                    reason='عيوب تصنيع / كسر أثناء النقل',
                    created_by=self.admin,
                )
                p = random.choice(products) if products else None
                if p:
                    SalesReturnLine.objects.create(
                        sales_return=sr,
                        product=p,
                        quantity=Decimal(random.randint(1, 5)),
                        unit_price=p.selling_price or Decimal('100'),
                    )
                sr.calculate_totals()
                sr.create_journal_entry()

        self.d('مرتجعات المبيعات', run)

    # ───────────────────────────────── purchase returns ─────────────────────────────────
    def make_purchase_returns(self):
        from purchase_returns.models import PurchaseReturn, PurchaseReturnLine
        from purchases.models import Product, PurchaseInvoice, Supplier

        def run():
            if PurchaseReturn.objects.exists():
                return
            suppliers = list(Supplier.objects.all())
            products = list(Product.objects.all())
            invoices = list(PurchaseInvoice.objects.all())
            for i in range(1, 6):
                supp = random.choice(suppliers) if suppliers else None
                inv = random.choice(invoices) if invoices else None
                pr = PurchaseReturn.objects.create(
                    return_number=f'PR-2026-{i:04d}',
                    date=self.today - timedelta(days=random.randint(1, 25)),
                    supplier=supp,
                    original_invoice=inv,
                    reason='مواد غير مطابقة للمواصفات',
                    created_by=self.admin,
                )
                p = random.choice(products) if products else None
                if p:
                    PurchaseReturnLine.objects.create(
                        purchase_return=pr,
                        product=p,
                        quantity=Decimal(random.randint(1, 5)),
                        unit_price=p.purchase_price or Decimal('80'),
                    )
                pr.calculate_totals()
                pr.create_journal_entry()

        self.d('مرتجعات المشتريات', run)

    # ───────────────────────────────── bank reconciliation ─────────────────────────────────
    def make_bank_reconciliation(self):
        from bank_reconciliation.models import BankStatementItem, ReconciliationSession
        from treasury.models import Bank

        def run():
            if ReconciliationSession.objects.exists():
                return
            bank = Bank.objects.first()
            if not bank:
                return
            session = ReconciliationSession.objects.create(
                bank_account=bank,
                period_start=self.today - timedelta(days=30),
                period_end=self.today,
                book_balance=bank.current_balance,
                bank_balance=bank.current_balance - Decimal('12000.00'),
                status='in_progress',
                created_by=self.admin,
            )
            session.calculate_difference()
            for i in range(1, 9):
                matched = random.random() > 0.4
                BankStatementItem.objects.create(
                    bank_account=bank,
                    transaction_date=self.today - timedelta(days=random.randint(1, 28)),
                    description=f'حركة بنكية رقم {i}',
                    reference=f'REF-{i:04d}',
                    debit_amount=Decimal(random.randint(0, 1)) * Decimal(random.randint(1000, 20000)),
                    credit_amount=Decimal(random.randint(0, 1)) * Decimal(random.randint(1000, 20000)),
                    status='matched' if matched else 'unmatched',
                )

        self.d('جلسات التسوية البنكية', run)

    # ───────────────────────────────── stock adjustments ─────────────────────────────────
    def make_stock_adjustments(self):
        from purchases.models import Product
        from stock_adjustments.models import StockAdjustment, StockAdjustmentLine
        from warehouses.models import Warehouse

        def run():
            if StockAdjustment.objects.exists():
                return
            warehouses = list(Warehouse.objects.all())
            products = list(Product.objects.all())
            for i, wh in enumerate(warehouses, 1):
                adj = StockAdjustment.objects.create(
                    adjustment_number=f'SA-2026-{i:03d}',
                    date=self.today - timedelta(days=random.randint(1, 20)),
                    adjustment_type=random.choice(['addition', 'count']),
                    warehouse=wh,
                    reason='جرد دوري وتصحيح أرصدة',
                    status='draft',
                    created_by=self.admin,
                )
                for p in products[:4]:
                    StockAdjustmentLine.objects.create(
                        adjustment=adj,
                        product=p,
                        quantity=Decimal(random.randint(5, 100)),
                        current_stock=Decimal(random.randint(10, 200)),
                    )
                adj.approve()

        self.d('تعديلات المخزون', run)

    # ───────────────────────────────── budget ─────────────────────────────────
    def make_budget(self):
        from accounts.models import Account
        from budget.models import Budget, CostCenter

        def run():
            if CostCenter.objects.count() == 0:
                parent = CostCenter.objects.create(
                    code='CC-00', name='المركز الرئيسي', description='الإدارة العامة', manager='المدير المالي'
                )
                subs = [
                    ('CC-01', 'مصنع الخرسانة'),
                    ('CC-02', 'قسم المقاولات'),
                    ('CC-03', 'قسم المبيعات'),
                    ('CC-04', 'قسم الصيانة'),
                ]
                for code, name in subs:
                    CostCenter.objects.create(code=code, name=name, parent=parent, description=f'مركز تكلفة {name}')
            if Budget.objects.count() == 0:
                centers = list(CostCenter.objects.all())
                accounts = Account.objects.filter(code__in=['6100', '7100', '8100', '8800', '8900'])
                for cc in centers:
                    for acc in accounts:
                        Budget.objects.create(
                            name=f'موازنة {acc.name} - {cc.name}',
                            account=acc,
                            cost_center=cc,
                            period='monthly',
                            year=2026,
                            month=7,
                            budgeted_amount=Decimal(random.randint(50000, 500000)),
                            actual_amount=Decimal(random.randint(40000, 520000)),
                            status='active',
                        )

        self.d('الموازنات ومراكز التكلفة', run)

    # ───────────────────────────────── credit notes ─────────────────────────────────
    def make_credit_notes(self):
        from credit_notes.models import CreditNote
        from purchases.models import PurchaseInvoice, Supplier
        from sales.models import Customer, SalesInvoice

        def run():
            if CreditNote.objects.exists():
                return
            customers = list(Customer.objects.all())
            suppliers = list(Supplier.objects.all())
            sinvoices = list(SalesInvoice.objects.all())
            pinvoices = list(PurchaseInvoice.objects.all())
            for i in range(1, 5):
                cust = random.choice(customers) if customers else None
                inv = random.choice(sinvoices) if sinvoices else None
                sub = Decimal(random.randint(1000, 15000))
                vat = sub * Decimal('0.14')
                CreditNote.objects.create(
                    note_type='credit_note',
                    note_number=f'CN-2026-{i:04d}',
                    date=self.today - timedelta(days=random.randint(1, 20)),
                    customer=cust,
                    original_sales_invoice=inv,
                    subtotal=sub,
                    vat_amount=vat,
                    total_amount=sub + vat,
                    reason='إشعار دائن لمرتجع مبيعات',
                    is_posted=True,
                )
            for i in range(1, 5):
                supp = random.choice(suppliers) if suppliers else None
                inv = random.choice(pinvoices) if pinvoices else None
                sub = Decimal(random.randint(1000, 12000))
                vat = sub * Decimal('0.14')
                CreditNote.objects.create(
                    note_type='debit_note',
                    note_number=f'DN-2026-{i:04d}',
                    date=self.today - timedelta(days=random.randint(1, 20)),
                    supplier=supp,
                    original_purchase_invoice=inv,
                    subtotal=sub,
                    vat_amount=vat,
                    total_amount=sub + vat,
                    reason='إشعار مدين لمرتجع مشتريات',
                    is_posted=True,
                )

        self.d('إشعارات المدين والدائن', run)

    # ───────────────────────────────── currency rates ─────────────────────────────────
    def make_currency_rates(self):
        from currency.models import Currency, ExchangeRateHistory

        def run():
            base = date(2026, 7, 13)
            for cur in Currency.objects.exclude(is_base=True):
                for d in range(1, 7):
                    ExchangeRateHistory.objects.get_or_create(
                        currency=cur,
                        date=base - timedelta(days=d * 5),
                        defaults={
                            'rate': cur.exchange_rate_to_egp * Decimal(str(1 + random.uniform(-0.02, 0.02))),
                            'notes': 'سجل تجريبي لسعر الصرف',
                        },
                    )

        self.d('سجلات أسعار صرف العملات', run)
