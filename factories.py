"""Factory Boy factories for test fixtures."""
import factory
from decimal import Decimal
from django.contrib.auth.models import User
from accounts.models import Account, AccountType, JournalEntry, JournalEntryLine
from purchases.models import Supplier, Product, ProductCategory, UnitOfMeasure, PurchaseInvoice, PurchaseInvoiceLine
from sales.models import Customer, SalesInvoice, SalesInvoiceLine


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    username = factory.Sequence(lambda n: f'user_{n:03d}')
    password = factory.PostGenerationMethodCall('set_password', 'test123')
    is_staff = False
    is_superuser = False


class AdminFactory(UserFactory):
    is_staff = True
    is_superuser = True
    username = 'admin'


class AccountTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AccountType
    name = factory.Sequence(lambda n: f'نوع حساب {n}')
    code = factory.Sequence(lambda n: f'AT{n:03d}')


class AccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Account
    code = factory.Sequence(lambda n: f'{1000 + n}')
    name = factory.Sequence(lambda n: f'حساب {n}')
    account_type = factory.SubFactory(AccountTypeFactory)
    current_balance = Decimal('0')


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer
    name = factory.Sequence(lambda n: f'عميل {n}')
    code = factory.Sequence(lambda n: f'C{n:03d}')
    phone = '0123456789'
    current_balance = Decimal('0')


class SupplierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Supplier
    name = factory.Sequence(lambda n: f'مورد {n}')
    code = factory.Sequence(lambda n: f'S{n:03d}')
    phone = '0123456789'
    current_balance = Decimal('0')


class ProductCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductCategory
    name = factory.Sequence(lambda n: f'فئة {n}')


class UnitOfMeasureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UnitOfMeasure
    name = 'قطعة'
    code = 'PCS'


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product
    code = factory.Sequence(lambda n: f'PRD{n:03d}')
    name = factory.Sequence(lambda n: f'منتج {n}')
    category = factory.SubFactory(ProductCategoryFactory)
    unit = factory.SubFactory(UnitOfMeasureFactory)
    purchase_price = Decimal('100')
    selling_price = Decimal('150')
