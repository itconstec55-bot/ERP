"""
Management command to seed the database with realistic Arabic dummy data.

Usage:
    python manage.py seed_dummy_data                          # Default: medium profile
    python manage.py seed_dummy_data --profile tiny           # Quick test (5 suppliers, etc.)
    python manage.py seed_dummy_data --profile small          # Small dataset
    python manage.py seed_dummy_data --profile medium         # Medium dataset (default)
    python manage.py seed_dummy_data --profile large          # Large dataset
    python manage.py seed_dummy_data --profile huge           # Huge dataset (100+ suppliers)

    # Override individual counts (overrides profile defaults):
    python manage.py seed_dummy_data --suppliers 50 --customers 100
    python manage.py seed_dummy_data --products 80 --invoices 30
    python manage.py seed_dummy_data --employees 25 --banks 5 --safes 3
    python manage.py seed_dummy_data --assets 20 --journals 30

    # With options:
    python manage.py seed_dummy_data --clear                  # Clear all data before generating
    python manage.py seed_dummy_data --seed 42                # Reproducible results
    python manage.py seed_dummy_data --profile large --seed 42 --clear

    # List available profiles:
    python manage.py seed_dummy_data --list-profiles
"""

from django.core.management.base import BaseCommand

from common.dummy_generator import PROFILES, DummyDataGenerator


class Command(BaseCommand):
    help = 'توليد بيانات تجريبية واقعية لجميع وحدات النظام'

    def add_arguments(self, parser):
        parser.add_argument(
            '--profile',
            type=str,
            default='medium',
            choices=list(PROFILES.keys()),
            help='ملف البيانات (tiny/small/medium/large/huge)',
        )
        parser.add_argument('--suppliers', type=int, default=None, help='عدد الموردين')
        parser.add_argument('--customers', type=int, default=None, help='عدد العملاء')
        parser.add_argument('--products', type=int, default=None, help='عدد المنتجات')
        parser.add_argument('--product-categories', type=int, default=None, help='عدد تصنيفات المنتجات')
        parser.add_argument('--invoices', type=int, default=None, help='عدد فواتير المشتريات')
        parser.add_argument('--sales', type=int, default=None, help='عدد فواتير المبيعات')
        parser.add_argument('--employees', type=int, default=None, help='عدد الموظفين')
        parser.add_argument('--departments', type=int, default=None, help='عدد الأقسام')
        parser.add_argument('--banks', type=int, default=None, help='عدد البنوك')
        parser.add_argument('--safes', type=int, default=None, help='عدد الخزائن')
        parser.add_argument('--assets', type=int, default=None, help='عدد الأصول الثابتة')
        parser.add_argument('--journals', type=int, default=None, help='عدد القيود المحاسبية')
        parser.add_argument('--bank-transactions', type=int, default=None, help='عدد المعاملات البنكية')
        parser.add_argument('--safe-transactions', type=int, default=None, help='عدد معاملات الخزائن')
        parser.add_argument('--depreciation-entries', type=int, default=None, help='عدد قيود الإهلاك')
        parser.add_argument('--salary-months', type=int, default=None, help='عدد أشهر الرواتب')
        parser.add_argument('--attendance-weeks', type=int, default=None, help='عدد أسابيع الحضور')
        parser.add_argument('--clear', action='store_true', help='مسح البيانات قبل التوليد')
        parser.add_argument('--seed', type=int, default=None, help='رقم البذرة لتوليد نتائج قابلة للتكرار')
        parser.add_argument('--list-profiles', action='store_true', help='عرض الملفات المتاحة')

    def handle(self, *args, **options):
        if options['list_profiles']:
            self.stdout.write(self.style.HTTP_INFO('  الملفات المتاحة:'))
            self.stdout.write('')
            for name, config in PROFILES.items():
                self.stdout.write(
                    f'  {name:10s} | '
                    f'موردين: {config["suppliers"]:3d} | '
                    f'عملاء: {config["customers"]:3d} | '
                    f'منتجات: {config["products"]:3d} | '
                    f'فواتير شراء: {config["purchase_invoices"]:3d} | '
                    f'فواتير بيع: {config["sales_invoices"]:3d} | '
                    f'موظفين: {config["employees"]:3d}'
                )
            self.stdout.write('')
            return

        overrides = {}
        override_map = {
            'suppliers': 'suppliers',
            'customers': 'customers',
            'products': 'products',
            'product_categories': 'product_categories',
            'invoices': 'purchase_invoices',
            'sales': 'sales_invoices',
            'employees': 'employees',
            'departments': 'departments',
            'banks': 'banks',
            'safes': 'safes',
            'assets': 'assets',
            'journals': 'journals',
            'bank_transactions': 'bank_transactions',
            'safe_transactions': 'safe_transactions',
            'depreciation_entries': 'depreciation_entries',
            'salary_months': 'salary_months',
            'attendance_weeks': 'attendance_weeks',
        }

        for cli_key, config_key in override_map.items():
            value = options.get(cli_key)
            if value is not None:
                overrides[config_key] = value

        generator = DummyDataGenerator(
            profile=options['profile'],
            seed=options['seed'],
            clear_first=options['clear'],
            progress_callback=lambda msg: self.stdout.write(msg),
            **overrides,
        )

        generator.generate()
