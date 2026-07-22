"""
Reusable Dummy Data Generator for the Accounting System.

This module provides a configurable, profile-based data generator that produces
realistic Arabic dummy data for all system modules. It can be used standalone
or integrated into Django management commands.

Usage (standalone):
    from common.dummy_generator import DummyDataGenerator
    gen = DummyDataGenerator(profile='medium', seed=42)
    results = gen.generate()

Usage (management command):
    python manage.py seed_dummy_data --profile large --clear
    python manage.py seed_dummy_data --suppliers 50 --customers 100 --seed 42
"""

import logging
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from faker import Faker

logger = logging.getLogger(__name__)

fake = Faker('ar_SA')

PROFILES = {
    'tiny': {
        'suppliers': 5,
        'customers': 5,
        'products': 10,
        'product_categories': 4,
        'purchase_invoices': 5,
        'sales_invoices': 5,
        'employees': 5,
        'departments': 3,
        'banks': 2,
        'safes': 2,
        'assets': 5,
        'journals': 5,
        'bank_transactions': 10,
        'safe_transactions': 10,
        'depreciation_entries': 5,
        'salary_months': 1,
        'attendance_weeks': 1,
    },
    'small': {
        'suppliers': 10,
        'customers': 15,
        'products': 20,
        'product_categories': 6,
        'purchase_invoices': 15,
        'sales_invoices': 20,
        'employees': 10,
        'departments': 4,
        'banks': 3,
        'safes': 2,
        'assets': 10,
        'journals': 10,
        'bank_transactions': 20,
        'safe_transactions': 15,
        'depreciation_entries': 10,
        'salary_months': 2,
        'attendance_weeks': 2,
    },
    'medium': {
        'suppliers': 20,
        'customers': 30,
        'products': 50,
        'product_categories': 8,
        'purchase_invoices': 40,
        'sales_invoices': 50,
        'employees': 25,
        'departments': 6,
        'banks': 4,
        'safes': 3,
        'assets': 20,
        'journals': 30,
        'bank_transactions': 40,
        'safe_transactions': 30,
        'depreciation_entries': 15,
        'salary_months': 3,
        'attendance_weeks': 4,
    },
    'large': {
        'suppliers': 50,
        'customers': 80,
        'products': 120,
        'product_categories': 10,
        'purchase_invoices': 100,
        'sales_invoices': 120,
        'employees': 50,
        'departments': 8,
        'banks': 6,
        'safes': 4,
        'assets': 40,
        'journals': 60,
        'bank_transactions': 80,
        'safe_transactions': 50,
        'depreciation_entries': 30,
        'salary_months': 6,
        'attendance_weeks': 8,
    },
    'huge': {
        'suppliers': 100,
        'customers': 200,
        'products': 300,
        'product_categories': 12,
        'purchase_invoices': 250,
        'sales_invoices': 300,
        'employees': 100,
        'departments': 10,
        'banks': 8,
        'safes': 5,
        'assets': 80,
        'journals': 120,
        'bank_transactions': 150,
        'safe_transactions': 100,
        'depreciation_entries': 60,
        'salary_months': 12,
        'attendance_weeks': 16,
    },
}

EGYPTIAN_CITIES = [
    'القاهرة',
    'الجيزة',
    'الإسكندرية',
    'المنصورة',
    'طنطا',
    'أسيوط',
    'سوهاج',
    'أسوان',
    'الفيوم',
    'بني سويف',
    'الزقازيق',
    'دمياط',
    'الإسماعيلية',
    'بورسعيد',
    'السويس',
    'كفر الشيخ',
    'المحلة الكبرى',
    'شرم الشيخ',
    'حلوان',
    '6 أكتوبر',
]

EGYPTIAN_BANKS = [
    ('البنك الأهلي المصري', 'NBE'),
    ('بنك CIB', 'CIB'),
    ('بنك مصر', 'Banque Misr'),
    ('بنك QNB', 'QNB'),
    ('بنك القاهرة', 'BCE'),
    ('البنك التجاري الدولي', 'CIB'),
    ('بنك قناة السويس', 'SBE'),
    ('مصرف الإنماء', 'AI'),
]

DEPARTMENT_DATA = [
    ('الإدارة العامة', 'إدارة', 'مسؤول عن الشؤون الإدارية العامة'),
    ('المبيعات', 'مبيعات', 'مسؤول عن عمليات البيع والتسويق'),
    ('المشتريات', 'مشتريات', 'مسؤول عن المشتريات والتوريد'),
    ('المحاسبة والمالية', 'محاسبة', 'مسؤول عن الدورات المحاسبية والإقرارات'),
    ('الموارد البشرية', 'موارد بشرية', 'مسؤول عن شؤون الموظفين'),
    ('التخزين والنقل', 'لوجستيات', 'مسؤول عن المخازن والنقل'),
    ('خدمة العملاء', 'خدمة عملاء', 'مسؤول عن خدمة ما بعد البيع'),
    ('التكنولوجيا', 'تقنية معلومات', 'مسؤول عن البنية التحتية لل technology'),
    ('التسويق', 'تسويق', 'مسؤول عن التسويق والإعلان'),
    ('الجودة', 'جودة', 'مسؤول عن معايير الجودة والمطابقة'),
]

PRODUCT_CATEGORIES_DATA = [
    ('إلكترونيات', 'أجهزة إلكترونية ومعدات تقنية'),
    ('أثاث مكتبي', 'طاولات وكراسي ودواليب مكتبية'),
    ('قرطاسية', 'أدوات مكتبية ومستلزمات إدارية'),
    ('ملابس', 'ملابس رجالية ونسائية متنوعة'),
    ('مواد غذائية', 'مواد غذائية أساسية ومشروبات'),
    ('مواد خام', 'مواد أولية للتصنيع والانتاج'),
    ('قطع غيار', 'قطع غيار سيارات ومعدات'),
    ('أدوات صناعية', 'أدوات ومعدات صناعية وميكانيكية'),
    ('مواد بناء', 'مواد بناء وتشييد'),
    ('كيماويات', 'مواد كيماوية صناعية وزراعية'),
]

PRODUCT_NAMES_BY_CATEGORY = {
    'إلكترونيات': [
        'لابتوب HP ProBook',
        'شاشة Samsung 24 بوصة',
        'لوحة مفاتيح لاسلكية',
        'ماوس لاسلكي Logitech',
        'طابعة Canon Laser',
        'سماعات Sony',
        'جهاز عرض Epson',
        'كيبورد ميكانيكي',
        'هارد ديسك خارجي 1TB',
        'раутer TP-Link',
        'سلسلة تغذية كهربائية',
        'UPS احتياطي',
    ],
    'أثاث مكتبي': [
        'كرسي مكتب مريح',
        'طاولة إدارية',
        'خزانة أوراق 4 درج',
        'كرسي انتظار',
        'طاولة اجتماعات',
        'رف مrecords',
        'مكتب موظف',
        'خزانة زجاجية',
        'ستارة شمسية',
    ],
    'قرطاسية': [
        'دفتر A4 مقوى',
        'قلم تروسيلا 0.5',
        'ورق طباعة A4 كرتون',
        'ملفات فلوبية',
        'استيكر ملون',
        'قلم تعليمي ألوان',
        'مسطرة معدنية',
        'مقص مكتبي',
        'دباسة مكتبية',
    ],
    'ملابس': [
        'قميص قطن رجالي',
        'بنطلون جينز',
        'جاكيت شتوي',
        'فستان صيفي',
        'تيشيرت قطن',
        'حذاء رسمي',
        'نظارة شمسية',
        'حقيبة يد',
        'ساعة يد',
    ],
    'مواد غذائية': [
        'أرز بسمتي 5 كجم',
        'زيت زيتون نقي',
        'سكر أبيض كرتون',
        'مكرونة إيطالية',
        'شاي أحمر علب',
        'قهوة تركية',
        'عسل طبيعي',
        'تمر مجدول',
        'حبة البركة',
    ],
    'مواد خام': [
        'خام قطن مصري',
        'سلك نحاسي 2 مم',
        'بلاستيك PE أكياس',
        'حديد تسليح 12 مم',
        'ألمنيوم صفائح',
        'خشب زان قطع',
        'جلد صناعي',
        'foyton نسيج',
        'رمل زجاجي',
    ],
    'قطع غيار': [
        'فرامل أمامية سيارة',
        'فلتر زيت محرك',
        'شمعات إشعال',
        'بطارية سيارة 60 أمبير',
        'مكيف سيارة',
        'مruleة عادم',
        'كمبروسر مكيف',
        'دينام شحن',
        'مساحات زجاج',
    ],
    'أدوات صناعية': [
        'مفتاح ربط هيدروليكي',
        'مفك براغي كهربائي',
        'شاكوش كهربائي',
        'جهاز لحام',
        'compressor هوائي',
        'منشار دائري',
        'زاوية حدادة',
        'مقياس ضبط',
        'toolsset صناعية',
    ],
    'مواد بناء': [
        'أسمنت بورتلاند',
        'حديد تسليح',
        'رمل بناء',
        'حصى عقدة',
        'بلاط أرضيات',
        'طلاء جدران',
        'عوازل مائية',
        'أنابيب PVC',
        'أسلاك كهربائية',
    ],
    'كيماويات': [
        'مادة تبييض كلور',
        'مادة عازلة',
        'مادة حافظة خشب',
        'دهان زنك',
        'مادة تنظيف صناعية',
        'مذيب كيميائي',
        'مادة لاصقة صناعية',
        'مبيد حشري',
        'سماد زراعي NPK',
    ],
}

SUPPLIER_NAMES = [
    'شركة الأهرام للتجارة',
    'مورد النيل للإلكترونيات',
    'شركة البركة للمواد الغذائية',
    'مؤسسة الرائد للأدوات المكتبية',
    'شركة مصر للزيوت والشحوم',
    'مورد الشرق للإلكترونيات',
    'شركة السلام للمواد الأولية',
    'مؤسسة الفجر للأدوات الصناعية',
    'شركة النصر للأثاث',
    'شركة الجيزة للبلاستيك',
    'مؤسسة المروج للإلكترونيات',
    'شركة الدلتا للملابس',
    'مورد الصعيد للغزل والنسيج',
    'شركة الإسكندرية للتجارة',
    'مؤسسة البدر لل建材',
    'شركة المجد للإلكترونيات',
    'مورد الهرم للإلكترونيات',
    'شركة السعيد للProducts',
    'مؤسسة التكنو للخدمات',
    'شركة رويال للتجارة العامة',
]

CUSTOMER_NAMES = [
    'شركة النيل للتجارة',
    'مؤسسة الفجر للأفراد',
    'شركة المجد للإلكترونيات',
    'شركة الأمل للمواد الغذائية',
    'مؤسسة البدر للملابس',
    'شركة السماح للتجارة',
    'شركة الكرمل للأثاث',
    'مؤسسة تكنو مصر',
    'شركة دلتا للتجارة العامة',
    'مؤسسة النور للأدوات',
    'شركة رويال للإلكترونيات',
    'مؤسسة سمارت للخدمات',
    'شركة بريمير للملابس',
    'مؤسسة سفن ستار',
    'شركة توب لاين',
    'شركة الماس للتجارة',
    'مؤسسة الزهراء',
    'شركة الأمانة',
    'مؤسسة الإبداع',
    'شركة المستقبل',
]

ASSET_NAMES = [
    'كمبيوتر مكتبي Dell OptiPlex',
    'لابتوب Lenovo ThinkPad',
    'طابعة HP LaserJet Pro',
    'شاشة Samsung 24 بوصة',
    'طاولة إدارية خشب',
    'كرسي مدير مريح',
    'خزانة أوراق 5 درج',
    'جهاز عرض Epson',
    'سبورة ذكية 75 بوصة',
    'آلة تجليد',
    'ماكينة تصوير Canon',
    'فرن صناعي',
    'شاحنة نقل 3.5 طن',
    'سيارة إدارية',
    'حفارة صغيرة',
    'مكيف مركزي',
    'جهاز تبريد صناعي',
    'ماكينة خياطة صناعية',
    'رافعة شوكية',
    'compressor هوائي كبير',
]

POSITIONS = [
    'مدير عام',
    'مدير مبيعات',
    'محاسب رئيسي',
    'مندوب مبيعات',
    'مدير مشتريات',
    'مسؤول مخزون',
    'موظف إداري',
    'مبرمج',
    'مشرف إنتاج',
    'كاتب',
    'مدير موارد بشرية',
    'مسؤول خدمة عملاء',
    'سائق',
    'عامل نقل',
    'مدير تسويق',
    'محلل بيانات',
    'مهندس جودة',
    'مشرف مستودع',
    'محاسب',
    'أمين صندوق',
    'ممتحن جودة',
    'فني صيانة',
]

JOURNAL_DESCRIPTIONS = [
    ('general', 'قيد عام - شراء مستلزمات مكتبية'),
    ('general', 'قيد عام - سداد مبلغ للمورد'),
    ('general', 'قيد عام - تحصيل مبلغ من العميل'),
    ('purchase', 'قيد مشتريات - فاتورة مورد'),
    ('sale', 'قيد مبيعات - فاتورة عميل'),
    ('receipt', '扣 تحصيل - تحصيل مبلغ من عميل'),
    ('payment', 'قيد دفع - دفع مبلغ للمورد'),
    ('adjustment', '扣 تسوية - تسوية أرصدة期末ية'),
    ('adjustment', '扣 تسوية - تسويغ فروقات'),
    ('general', 'قيد عام - إيراد متنوع'),
]


class DummyDataGenerator:
    """
    Configurable dummy data generator for the accounting system.

    Supports profiles (tiny/small/medium/large/huge) and individual overrides.
    All generated data is fake and contains no real sensitive information.
    """

    def __init__(
        self,
        profile: str = 'medium',
        seed: int | None = None,
        clear_first: bool = False,
        progress_callback=None,
        **overrides,
    ):
        if profile not in PROFILES:
            raise ValueError(f"Unknown profile '{profile}'. Available: {list(PROFILES.keys())}")

        self.config = dict(PROFILES[profile])
        self.config.update(overrides)
        self.seed = seed
        self.clear_first = clear_first
        self.progress_callback = progress_callback
        self.results = {}

        if seed is not None:
            random.seed(seed)
            Faker.seed(seed)

    def _report(self, message: str):
        logger.info(message)
        if self.progress_callback:
            self.progress_callback(message)

    def _d(self, value):
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _random_phone(self):
        prefix = random.choice(['02', '03', '04', '08', '09'])
        return f'{prefix}{random.randint(10000000, 99999999)}'

    def _random_mobile(self):
        return f'01{random.choice(["0", "1", "2", "5", "6", "8"])}{random.randint(10000000, 99999999)}'

    def _random_email(self, name: str):
        clean = name.replace(' ', '').replace('ة', 'a').replace('ي', 'y')
        domains = ['test.com', 'demo.local', 'example.org', 'mail.test']
        return f'{clean}{random.randint(1, 999)}@{random.choice(domains)}'

    def _random_national_id(self):
        return f'{random.randint(25000000000000, 32999999999999)}'

    def _random_tax_number(self, prefix: int = 2):
        return f'{prefix}{random.randint(100000000, 999999999)}'

    def _random_iban(self):
        return f'EG{random.randint(10, 30)}{random.randint(100000000000000000, 999999999999999999)}'

    def generate(self):
        from django.contrib.auth.models import User

        if self.clear_first:
            self._clear_all()

        self._report('=' * 60)
        self._report('  جاري توليد البيانات التجريبية...')
        self._report('=' * 60)

        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            import os

            admin_password = os.environ.get('DJANGO_ADMIN_PASSWORD', 'ChangeMe!2024')
            admin_user = User.objects.create_superuser('admin', 'admin@test.com', admin_password)
            self._report('  [OK] تم إنشاء مستخدم admin')

        self._seed_departments()
        self._seed_employees(admin_user)
        self._ensure_treasury_accounts()
        self._seed_suppliers()
        self._seed_product_categories()
        self._seed_products()
        self._seed_customers()
        self._seed_banks()
        self._seed_safes()
        self._seed_purchase_invoices(admin_user)
        self._seed_sales_invoices(admin_user)
        self._seed_asset_categories()
        self._seed_assets(admin_user)
        self._seed_bank_transactions(admin_user)
        self._seed_safe_transactions(admin_user)
        self._seed_depreciation_entries(admin_user)
        self._seed_salaries(admin_user)
        self._seed_attendance()
        self._seed_journal_entries(admin_user)

        self._report('')
        self._report('=' * 60)
        self._report('  تم توليد البيانات بنجاح!')
        self._report('=' * 60)
        self._print_summary()

        return self.results

    def _clear_all(self):
        from accounts.models import JournalEntry, JournalEntryLine
        from assets.models import Asset, AssetCategory, DepreciationEntry
        from hr.models import Attendance, Department, Employee, Salary
        from purchases.models import Product, ProductCategory, PurchaseInvoice, PurchaseInvoiceLine, Supplier
        from sales.models import Customer, SalesInvoice, SalesInvoiceLine
        from treasury.models import Bank, BankTransaction, Safe, SafeTransaction

        self._report('جاري مسح البيانات...')
        for model in [
            Attendance,
            Salary,
            Employee,
            Department,
            DepreciationEntry,
            Asset,
            AssetCategory,
            BankTransaction,
            SafeTransaction,
            Bank,
            Safe,
            SalesInvoiceLine,
            SalesInvoice,
            Customer,
            PurchaseInvoiceLine,
            PurchaseInvoice,
            Product,
            ProductCategory,
            Supplier,
            JournalEntryLine,
            JournalEntry,
        ]:
            model.objects.all().delete()
        self._report('  [OK] تم مسح جميع البيانات')

    def _seed_departments(self):
        from hr.models import Department

        count = self.config['departments']
        departments = []
        for name, mgr_key, desc in DEPARTMENT_DATA[:count]:
            dept, _ = Department.objects.get_or_create(
                name=name, defaults={'manager': fake.name_male(), 'description': desc}
            )
            departments.append(dept)
        self.results['departments'] = departments
        self._report(f'  [OK] {len(departments)} أقسام')

    def _seed_employees(self, user):
        from hr.models import Department, Employee

        count = self.config['employees']
        departments = list(Department.objects.all())
        employees = []
        used_ids = set()

        for i in range(count):
            gender = random.choice(['male', 'female'])
            first_name = fake.name_male() if gender == 'male' else fake.name_female()
            last_name = fake.name_male() if gender == 'male' else fake.name_female()

            national_id = self._random_national_id()
            while national_id in used_ids:
                national_id = self._random_national_id()
            used_ids.add(national_id)

            emp, _ = Employee.objects.get_or_create(
                employee_number=f'EMP{i + 1:04d}',
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'national_id': national_id,
                    'gender': gender,
                    'date_of_birth': fake.date_of_birth(minimum_age=22, maximum_age=55),
                    'marital_status': random.choice(['single', 'married', 'married', 'married']),
                    'department': random.choice(departments) if departments else None,
                    'position': random.choice(POSITIONS),
                    'hire_date': fake.date_between(start_date='-5y', end_date='-1y'),
                    'phone': self._random_phone(),
                    'mobile': self._random_mobile(),
                    'email': self._random_email(f'{first_name}{last_name}'),
                    'address': f'{random.choice(EGYPTIAN_CITIES)} - {fake.street_name()}',
                    'salary': random.choice([8000, 10000, 12000, 15000, 18000, 22000, 25000, 30000]),
                    'social_insurance_number': f'{random.randint(100000000, 999999999)}',
                    'tax_number': self._random_tax_number(3),
                    'bank_account': f'{random.randint(1000000000000000, 9999999999999999)}',
                    'status': 'active',
                },
            )
            employees.append(emp)
        self.results['employees'] = employees
        self._report(f'  [OK] {len(employees)} موظفين')

    def _ensure_treasury_accounts(self):
        from accounts.models import Account, AccountType

        try:
            acc_type = AccountType.objects.get(code='AT01')
            Account.objects.get_or_create(
                code='1610', defaults={'name': 'البنك الأهلي المصري', 'account_type': acc_type, 'is_bank': True}
            )
        except Exception as e:
            logger.exception('Failed to ensure treasury accounts: %s', e)

    def _seed_suppliers(self):
        from purchases.models import Supplier

        count = self.config['suppliers']
        suppliers = []
        used_codes = set()

        for i in range(count):
            code = f'SUP{i + 1:04d}'
            name = SUPPLIER_NAMES[i] if i < len(SUPPLIER_NAMES) else f'مورد {fake.company()}'
            city = random.choice(EGYPTIAN_CITIES)

            sup, _ = Supplier.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'supplier_type': random.choice(['company', 'company', 'individual']),
                    'tax_number': self._random_tax_number(2),
                    'commercial_register': f'{random.randint(100000, 999999)}',
                    'address': f'{city} - {fake.street_name()}',
                    'city': city,
                    'phone': self._random_phone(),
                    'mobile': self._random_mobile(),
                    'email': self._random_email(f'supplier{i + 1}'),
                    'credit_limit': random.choice([50000, 100000, 200000, 500000]),
                    'current_balance': self._d(random.randint(0, 100000)),
                    'notes': random.choice([None, 'مورد موثوق', 'يوجد اتفاقية أسعار', '']),
                },
            )
            suppliers.append(sup)
        self.results['suppliers'] = suppliers
        self._report(f'  [OK] {len(suppliers)} موردين')

    def _seed_product_categories(self):
        from purchases.models import ProductCategory

        count = self.config['product_categories']
        categories = []
        for name, desc in PRODUCT_CATEGORIES_DATA[:count]:
            cat, _ = ProductCategory.objects.get_or_create(name=name, defaults={'description': desc})
            categories.append(cat)
        self.results['categories'] = categories
        self._report(f'  [OK] {len(categories)} تصنيفات منتجات')

    def _seed_products(self):
        from purchases.models import Product, ProductCategory

        count = self.config['products']
        categories = list(ProductCategory.objects.all())
        units = ['قطعة', 'كرتونة', 'كيلو', 'متر', 'علبة', 'دزينة', 'رول', 'لتر', 'bundle']
        products = []

        all_names = []
        for cat_name, names in PRODUCT_NAMES_BY_CATEGORY.items():
            all_names.extend(names)

        for i in range(count):
            if i < len(all_names):
                name = all_names[i]
            else:
                name = f'منتج {fake.word()} {random.randint(1, 999)}'

            purchase_price = self._d(random.uniform(10, 5000))
            markup = self._d(random.uniform(1.15, 1.50))
            selling_price = (purchase_price * markup).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            cat = random.choice(categories) if categories else None
            prod, _ = Product.objects.get_or_create(
                code=f'PRD{i + 1:04d}',
                defaults={
                    'name': name,
                    'category': cat,
                    'unit': random.choice(units),
                    'purchase_price': purchase_price,
                    'selling_price': selling_price,
                    'current_stock': self._d(random.randint(0, 500)),
                    'minimum_stock': self._d(random.randint(5, 50)),
                    'vat_rate': Decimal('14.00'),
                },
            )
            products.append(prod)
        self.results['products'] = products
        self._report(f'  [OK] {len(products)} منتجات')

    def _seed_customers(self):
        from sales.models import Customer

        count = self.config['customers']
        customers = []
        for i in range(count):
            name = CUSTOMER_NAMES[i] if i < len(CUSTOMER_NAMES) else f'عميل {fake.company()}'
            city = random.choice(EGYPTIAN_CITIES)
            cust, _ = Customer.objects.get_or_create(
                code=f'CUS{i + 1:04d}',
                defaults={
                    'name': name,
                    'customer_type': random.choice(['company', 'company', 'individual', 'government']),
                    'tax_number': self._random_tax_number(3),
                    'commercial_register': f'{random.randint(100000, 999999)}',
                    'address': f'{city} - {fake.street_name()}',
                    'city': city,
                    'phone': self._random_phone(),
                    'mobile': self._random_mobile(),
                    'email': self._random_email(f'customer{i + 1}'),
                    'credit_limit': random.choice([100000, 200000, 500000, 1000000]),
                    'current_balance': self._d(random.randint(-50000, 200000)),
                    'notes': random.choice([None, 'عميل VIP', 'يوجد خصم خاص', '']),
                },
            )
            customers.append(cust)
        self.results['customers'] = customers
        self._report(f'  [OK] {len(customers)} عملاء')

    def _seed_banks(self):
        from treasury.models import Bank

        count = self.config['banks']
        banks = []
        for i in range(count):
            if i < len(EGYPTIAN_BANKS):
                name, swift = EGYPTIAN_BANKS[i]
            else:
                name = f'بنك {fake.company()}'
                swift = f'BK{random.randint(100, 999)}'

            branch = f'فرع {random.choice(EGYPTIAN_CITIES)}'
            bank, _ = Bank.objects.get_or_create(
                name=name,
                defaults={
                    'branch': branch,
                    'account_number': f'{random.randint(1000000000000000, 9999999999999999)}',
                    'iban': self._random_iban(),
                    'swift_code': swift,
                    'current_balance': self._d(random.randint(50000, 1000000)),
                },
            )
            banks.append(bank)
        self.results['banks'] = banks
        self._report(f'  [OK] {len(banks)} بنوك')

    def _seed_safes(self):
        from treasury.models import Safe

        count = self.config['safes']
        safes_data = [
            ('خزينة المكتب الرئيسي', 'أحمد محمد', 200000),
            ('خزينة المستودع', 'محمد علي', 100000),
            ('خزينة الفرع', 'خالد أحمد', 150000),
            ('خزينة المبيعات', 'سارة حسن', 80000),
            ('خزينة التجزئة', 'نورا عادل', 120000),
        ]
        safes = []
        for i in range(count):
            if i < len(safes_data):
                name, person, limit = safes_data[i]
            else:
                name = f'خزينة {fake.word()}'
                person = fake.name_male()
                limit = random.randint(50000, 200000)

            safe, _ = Safe.objects.get_or_create(
                name=name,
                defaults={
                    'responsible_person': person,
                    'current_balance': self._d(random.randint(5000, limit // 2)),
                    'maximum_limit': self._d(limit),
                },
            )
            safes.append(safe)
        self.results['safes'] = safes
        self._report(f'  [OK] {len(safes)} خزائن')

    def _seed_purchase_invoices(self, user):
        from purchases.models import Product, PurchaseInvoice, PurchaseInvoiceLine, Supplier

        count = self.config['purchase_invoices']
        suppliers = list(Supplier.objects.all())
        products = list(Product.objects.all())
        if not suppliers or not products:
            self._report('  [SKIP] لا توجد موردين أو منتجات لفواتير المشتريات')
            return

        today = date.today()
        days_back = min(self.config.get('attendance_weeks', 4) * 7 * 3, 365)
        created = 0

        for i in range(count):
            supplier = random.choice(suppliers)
            inv_date = today - timedelta(days=random.randint(0, days_back))
            is_tax = random.choice([True, True, True, False])

            invoice = PurchaseInvoice.objects.create(
                invoice_number=f'PUR-{inv_date.year}-{i + 1:04d}',
                supplier=supplier,
                date=inv_date,
                due_date=inv_date + timedelta(days=random.choice([15, 30, 60, 90])),
                payment_method=random.choice(['cash', 'credit', 'credit', 'transfer']),
                is_tax_invoice=is_tax,
                subtotal=0,
                vat_amount=0,
                total_amount=0,
                paid_amount=Decimal('0'),
                is_posted=False,
                created_by=user,
            )

            num_lines = random.randint(1, min(5, len(products)))
            selected_products = random.sample(products, num_lines)
            for prod in selected_products:
                qty = Decimal(str(random.randint(1, 50)))
                PurchaseInvoiceLine.objects.create(
                    invoice=invoice,
                    product=prod,
                    quantity=qty,
                    unit_price=prod.purchase_price,
                    discount_percent=random.choice([0, 0, 0, 5, 10]),
                )

            invoice.calculate_totals()
            paid = random.choice(
                [Decimal('0'), (invoice.total_amount * self._d(random.uniform(0.3, 1.0))), invoice.total_amount]
            )
            invoice.paid_amount = min(paid, invoice.total_amount)
            invoice.remaining_amount = invoice.total_amount - invoice.paid_amount
            invoice.save(update_fields=['paid_amount', 'remaining_amount'])
            created += 1
        self._report(f'  [OK] {created} فاتورة مشتريات')

    def _seed_sales_invoices(self, user):
        from purchases.models import Product
        from sales.models import Customer, SalesInvoice, SalesInvoiceLine

        count = self.config['sales_invoices']
        customers = list(Customer.objects.all())
        products = list(Product.objects.all())
        if not customers or not products:
            self._report('  [SKIP] لا توجد عملاء أو منتجات لفواتير المبيعات')
            return

        today = date.today()
        days_back = min(self.config.get('attendance_weeks', 4) * 7 * 3, 365)
        created = 0

        for i in range(count):
            customer = random.choice(customers)
            inv_date = today - timedelta(days=random.randint(0, days_back))
            is_tax = random.choice([True, True, True, False])

            invoice = SalesInvoice.objects.create(
                invoice_number=f'SAL-{inv_date.year}-{i + 1:04d}',
                customer=customer,
                date=inv_date,
                due_date=inv_date + timedelta(days=random.choice([15, 30, 60])),
                payment_method=random.choice(['cash', 'credit', 'transfer', 'cash']),
                is_tax_invoice=is_tax,
                subtotal=0,
                vat_amount=0,
                total_amount=0,
                paid_amount=Decimal('0'),
                cost_of_goods=0,
                gross_profit=0,
                is_posted=False,
                created_by=user,
            )

            num_lines = random.randint(1, min(4, len(products)))
            selected_products = random.sample(products, num_lines)
            for prod in selected_products:
                qty = Decimal(str(random.randint(1, 20)))
                SalesInvoiceLine.objects.create(
                    invoice=invoice,
                    product=prod,
                    quantity=qty,
                    unit_price=prod.selling_price,
                    cost_price=prod.purchase_price,
                    discount_percent=random.choice([0, 0, 0, 5, 10]),
                )

            invoice.calculate_totals()
            paid_pct = random.choice([0, 0.5, 0.8, 1.0])
            invoice.paid_amount = invoice.total_amount * self._d(paid_pct)
            invoice.remaining_amount = invoice.total_amount - invoice.paid_amount
            invoice.save(update_fields=['paid_amount', 'remaining_amount'])
            created += 1
        self._report(f'  [OK] {created} فاتورة مبيعات')

    def _seed_asset_categories(self):
        from assets.models import AssetCategory

        cats_data = [
            ('أجهزة كمبيوتر', 25),
            ('أثاث مكتبي', 10),
            ('آلات ومعدات', 15),
            ('سيارات', 20),
            ('أدوات مكتبية', 30),
            ('أجهزة كهربائية', 15),
        ]
        categories = []
        for name, rate in cats_data:
            cat, _ = AssetCategory.objects.get_or_create(name=name, defaults={'depreciation_rate': self._d(rate)})
            categories.append(cat)
        self.results['asset_categories'] = categories
        self._report(f'  [OK] {len(categories)} تصنيفات أصول')

    def _seed_assets(self, user):
        from assets.models import Asset, AssetCategory

        count = self.config['assets']
        categories = list(AssetCategory.objects.all())
        if not categories:
            self._report('  [SKIP] لا توجد تصنيفات أصول')
            return

        today = date.today()
        assets = []
        for i in range(count):
            name = ASSET_NAMES[i] if i < len(ASSET_NAMES) else f'أصل {fake.word()} {random.randint(1, 99)}'
            purchase_price = self._d(random.uniform(2000, 200000))
            useful_life = random.choice([3, 5, 7, 10])
            purchase_date = today - timedelta(days=random.randint(90, 365 * 3))
            accumulated = purchase_price * self._d(random.uniform(0.1, 0.7))

            asset, _ = Asset.objects.get_or_create(
                code=f'AST{i + 1:04d}',
                defaults={
                    'name': name,
                    'category': random.choice(categories),
                    'purchase_date': purchase_date,
                    'purchase_price': purchase_price,
                    'salvage_value': (purchase_price * Decimal('0.1')).quantize(Decimal('0.01')),
                    'useful_life_years': useful_life,
                    'depreciation_method': random.choice(['straight_line', 'straight_line', 'declining']),
                    'accumulated_depreciation': accumulated,
                    'net_book_value': purchase_price - accumulated,
                    'location': random.choice(['المكتب الرئيسي', 'المستودع', 'الفرع', 'المصنع']),
                    'status': random.choice(['active', 'active', 'active', 'depreciated']),
                    'created_by': user,
                },
            )
            assets.append(asset)
        self.results['assets'] = assets
        self._report(f'  [OK] {len(assets)} أصول ثابتة')

    def _seed_bank_transactions(self, user):
        from treasury.models import Bank, BankTransaction

        count = self.config['bank_transactions']
        banks = list(Bank.objects.all())
        if not banks:
            self._report('  [SKIP] لا توجد بنوك لمعاملات بنكية')
            return

        today = date.today()
        created = 0
        for i in range(count):
            bank = random.choice(banks)
            tx_type = random.choice(['deposit', 'withdrawal', 'transfer_in', 'transfer_out'])
            tx_date = today - timedelta(days=random.randint(0, 180))
            amount = self._d(random.randint(1000, 200000))

            BankTransaction.objects.create(
                bank=bank,
                transaction_type=tx_type,
                date=tx_date,
                amount=amount,
                reference_number=f'REF-{random.randint(100000, 999999)}',
                check_number=f'CHK-{random.randint(10000, 99999)}' if random.random() > 0.6 else None,
                description=f'معاملة {bank.name} - {tx_type}',
                created_by=user,
            )
            created += 1
        self._report(f'  [OK] {created} معاملة بنكية')

    def _seed_safe_transactions(self, user):
        from treasury.models import Safe, SafeTransaction

        count = self.config['safe_transactions']
        safes = list(Safe.objects.all())
        if not safes:
            self._report('  [SKIP] لا توجد خزائن لمعاملات خزينة')
            return

        today = date.today()
        created = 0
        for i in range(count):
            safe = random.choice(safes)
            tx_type = random.choice(['deposit', 'withdrawal', 'transfer'])
            tx_date = today - timedelta(days=random.randint(0, 180))
            amount = self._d(random.randint(500, 50000))

            SafeTransaction.objects.create(
                safe=safe,
                transaction_type=tx_type,
                date=tx_date,
                amount=amount,
                description=f'معاملة {safe.name} - {tx_type}',
                created_by=user,
            )
            created += 1
        self._report(f'  [OK] {created} معاملة خزينة')

    def _seed_depreciation_entries(self, user):
        from assets.models import Asset, DepreciationEntry

        count = self.config['depreciation_entries']
        assets = list(Asset.objects.filter(status='active'))
        if not assets:
            self._report('  [SKIP] لا توجد أصول نشطة لإدخالات الإهلاك')
            return

        today = date.today()
        created = 0
        for i in range(min(count, len(assets) * 3)):
            asset = random.choice(assets)
            months = random.choice([1, 3, 6])
            depr_amount = asset.calculate_depreciation_for_period(months)

            if depr_amount <= 0:
                continue

            depr_date = today - timedelta(days=random.randint(0, 365))
            DepreciationEntry.objects.create(
                asset=asset,
                date=depr_date,
                amount=depr_amount,
                accumulated_after=asset.accumulated_depreciation + depr_amount,
                months=months,
                notes=f'إهلاك {months} شهر - {asset.name}',
                created_by=user,
            )
            created += 1
        self._report(f'  [OK] {created} قيد إهلاك')

    def _seed_salaries(self, user):
        from hr.models import Employee, Salary

        employees = list(Employee.objects.all()[: self.config['employees']])
        salary_months = self.config.get('salary_months', 3)
        today = date.today()
        created = 0

        for emp in employees[:15]:
            for m in range(1, salary_months + 1):
                month = today.month - m
                year = today.year
                if month <= 0:
                    month += 12
                    year -= 1

                basic = emp.salary
                allowances = basic * self._d(random.uniform(0.1, 0.3))
                overtime = self._d(random.randint(0, 2000))
                bonus = self._d(random.randint(0, 1000))
                deductions = basic * self._d(random.uniform(0.02, 0.1))
                social_ins = (basic * Decimal('0.11')).quantize(Decimal('0.01'))
                income_tax = basic * self._d(random.uniform(0.05, 0.15))
                net = basic + allowances + overtime + bonus - deductions - social_ins - income_tax

                is_paid = random.choice([True, True, False])
                Salary.objects.get_or_create(
                    employee=emp,
                    month=month,
                    year=year,
                    defaults={
                        'basic_salary': basic,
                        'allowances': allowances,
                        'overtime': overtime,
                        'bonus': bonus,
                        'deductions': deductions,
                        'social_insurance': social_ins,
                        'income_tax': income_tax,
                        'net_salary': net,
                        'is_paid': is_paid,
                        'payment_date': today - timedelta(days=random.randint(0, 30)) if is_paid else None,
                    },
                )
                created += 1
        self._report(f'  [OK] {created} سجل رواتب')

    def _seed_attendance(self):
        from hr.models import Attendance, Employee

        employees = list(Employee.objects.all()[: self.config['employees']])
        weeks = self.config.get('attendance_weeks', 4)
        today = date.today()
        statuses = ['present', 'present', 'present', 'present', 'late', 'absent', 'leave', 'sick']
        created = 0

        for emp in employees[:15]:
            for d in range(1, weeks * 7 + 1):
                att_date = today - timedelta(days=d)
                if att_date.weekday() >= 5:
                    continue

                status = random.choice(statuses)
                check_in = f'0{random.randint(7, 9)}:{random.randint(0, 30):02d}'
                check_out = f'{random.randint(16, 19)}:{random.randint(0, 59):02d}'

                Attendance.objects.get_or_create(
                    employee=emp,
                    date=att_date,
                    defaults={
                        'check_in': check_in,
                        'check_out': check_out if status != 'absent' else None,
                        'status': status,
                        'overtime_hours': self._d(random.randint(0, 3)) if status == 'present' else Decimal('0'),
                    },
                )
                created += 1
        self._report(f'  [OK] {created} سجل حضور')

    def _seed_journal_entries(self, user):
        from accounts.models import Account, JournalEntry, JournalEntryLine

        count = self.config['journals']
        today = date.today()
        created = 0

        for i in range(count):
            entry_type, desc = random.choice(JOURNAL_DESCRIPTIONS)
            entry_date = today - timedelta(days=random.randint(0, 365))
            amount = self._d(random.randint(1000, 50000))

            entry = JournalEntry.objects.create(
                entry_number=f'JE-{entry_date.year}-{i + 1:04d}',
                entry_type=entry_type,
                date=entry_date,
                description=desc,
                reference=f'REF-{i + 1:04d}',
                is_posted=random.choice([True, True, False]),
                total_debit=amount,
                total_credit=amount,
                created_by=user,
            )

            try:
                debit_acc = Account.objects.filter(account_type__account_type='asset').first()
                credit_acc = Account.objects.filter(account_type__account_type='liability').first()
                if debit_acc and credit_acc:
                    JournalEntryLine.objects.create(
                        journal_entry=entry, account=debit_acc, debit=amount, credit=0, description='مدين'
                    )
                    JournalEntryLine.objects.create(
                        journal_entry=entry, account=credit_acc, debit=0, credit=amount, description='دائن'
                    )
            except Exception as e:
                logger.warning(f'Failed to create journal entry lines: {e}')

            created += 1
        self._report(f'  [OK] {created} قيد محاسبي')

    def _print_summary(self):
        from accounts.models import Account, JournalEntry
        from assets.models import Asset
        from hr.models import Attendance, Employee, Salary
        from purchases.models import Product, PurchaseInvoice, Supplier
        from sales.models import Customer, SalesInvoice
        from treasury.models import Bank, BankTransaction, Safe, SafeTransaction

        self._report('')
        self._report('  --- ملخص البيانات ---')
        counts = [
            ('الحسابات', Account.objects.count()),
            ('الموردين', Supplier.objects.count()),
            ('المنتجات', Product.objects.count()),
            ('العملاء', Customer.objects.count()),
            ('فواتير المشتريات', PurchaseInvoice.objects.count()),
            ('فواتير المبيعات', SalesInvoice.objects.count()),
            ('البنوك', Bank.objects.count()),
            ('الخزائن', Safe.objects.count()),
            ('المعاملات البنكية', BankTransaction.objects.count()),
            ('معاملات الخزائن', SafeTransaction.objects.count()),
            ('الأصول', Asset.objects.count()),
            ('الموظفين', Employee.objects.count()),
            ('سجلات الرواتب', Salary.objects.count()),
            ('سجلات الحضور', Attendance.objects.count()),
            ('القيود المحاسبية', JournalEntry.objects.count()),
        ]
        for name, count in counts:
            self._report(f'    {name}: {count}')
        self._report('')
