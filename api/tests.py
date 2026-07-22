from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from access_control.models import Role, Screen, UserRoleAssignment
from common.models import UserProfile
from common.permissions import get_user_profile

# ─── fixtures ───


@pytest.fixture
def staff_user(db):
    return User.objects.create_user('staff1', 'staff1@test.com', 'pass1234', is_staff=True)


@pytest.fixture
def owner_user(db):
    return User.objects.create_user('owner', 'owner@test.com', 'pass1234')


@pytest.fixture
def other_user(db):
    return User.objects.create_user('other', 'other@test.com', 'pass1234')


@pytest.fixture
def fresh_client():
    return APIClient()


@pytest.fixture
def staff_client(fresh_client, staff_user):
    token, _ = Token.objects.get_or_create(user=staff_user)
    fresh_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return fresh_client


@pytest.fixture
def owner_client(fresh_client, owner_user):
    token, _ = Token.objects.get_or_create(user=owner_user)
    fresh_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return fresh_client


# ═══════════════════════════════════════════════════════════════
#  1.  IsAdminOrReadOnly
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIsAdminOrReadOnly:
    """اختبار صلاحية IsAdminOrReadOnly"""

    def test_authenticated_user_can_list(self, staff_client, staff_user):
        """المستخدم المصادق عليه يستطيع قراءة القائمة"""
        resp = staff_client.get('/api/v1/users')
        assert resp.status_code == status.HTTP_200_OK

    def test_non_staff_user_can_list(self, auth_api_client):
        """المستخدم العادي يستطيع القراءة"""
        resp = auth_api_client.get('/api/v1/users')
        assert resp.status_code == status.HTTP_200_OK

    def test_unauthenticated_user_denied(self, fresh_client):
        """المستخدم غير المصادق عليه مرفوض"""
        resp = fresh_client.get('/api/v1/users')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_permission_class_on_read(self):
        """القراءة (GET/HEAD/OPTIONS) مسموحة لأي مستخدم مصادق"""
        from api.permissions import IsAdminOrReadOnly

        perm = IsAdminOrReadOnly()
        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, is_staff=False)
        view = MagicMock()
        for method in ('GET', 'HEAD', 'OPTIONS'):
            request.method = method
            assert perm.has_permission(request, view) is True

    def test_permission_class_blocks_write_for_non_staff(self):
        """الكتابة مرفوضة لغير staff"""
        from api.permissions import IsAdminOrReadOnly

        perm = IsAdminOrReadOnly()
        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, is_staff=False)
        request.method = 'POST'
        view = MagicMock()
        assert perm.has_permission(request, view) is False

    def test_permission_class_allows_write_for_staff(self):
        """الكتابة مسموحة لـ staff"""
        from api.permissions import IsAdminOrReadOnly

        perm = IsAdminOrReadOnly()
        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, is_staff=True)
        request.method = 'POST'
        view = MagicMock()
        assert perm.has_permission(request, view) is True


# ═══════════════════════════════════════════════════════════════
#  2.  IsOwnerOrReadOnly
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIsOwnerOrReadOnly:
    """اختبار صلاحية IsOwnerOrReadOnly"""

    def test_read_always_allowed(self):
        """القراءة مسموحة دائماً"""
        from api.permissions import IsOwnerOrReadOnly

        perm = IsOwnerOrReadOnly()
        request = MagicMock()
        request.method = 'GET'
        view = MagicMock()
        obj = MagicMock()
        assert perm.has_object_permission(request, view, obj) is True

    def test_owner_can_write(self, owner_user):
        """المالك يستطيع الكتابة"""
        from api.permissions import IsOwnerOrReadOnly

        perm = IsOwnerOrReadOnly()
        request = MagicMock()
        request.method = 'POST'
        request.user = owner_user
        view = MagicMock()
        obj = MagicMock(created_by=owner_user)
        assert perm.has_object_permission(request, view, obj) is True

    def test_non_owner_denied_write(self, other_user, owner_user):
        """غير المالك مرفوض الكتابة"""
        from api.permissions import IsOwnerOrReadOnly

        perm = IsOwnerOrReadOnly()
        request = MagicMock()
        request.method = 'DELETE'
        request.user = other_user
        view = MagicMock()
        obj = MagicMock(created_by=owner_user)
        assert perm.has_object_permission(request, view, obj) is False

    def test_staff_fallback_when_no_created_by(self, staff_user):
        """staff يمكنه الكتابة عندما لا يوجد created_by"""
        from api.permissions import IsOwnerOrReadOnly

        perm = IsOwnerOrReadOnly()
        request = MagicMock()
        request.method = 'PUT'
        request.user = staff_user
        view = MagicMock()
        obj = MagicMock(spec=[])  # no created_by attribute
        assert perm.has_object_permission(request, view, obj) is True

    def test_non_staff_denied_when_no_created_by(self, other_user):
        """مستخدم عادي مرفوض عندما لا يوجد created_by"""
        from api.permissions import IsOwnerOrReadOnly

        perm = IsOwnerOrReadOnly()
        request = MagicMock()
        request.method = 'POST'
        request.user = other_user
        view = MagicMock()
        obj = MagicMock(spec=[])  # no created_by
        assert perm.has_object_permission(request, view, obj) is False


# ═══════════════════════════════════════════════════════════════
#  3.  IsAuthenticatedOrReadOnly
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIsAuthenticatedOrReadOnly:
    """اختبار صلاحية IsAuthenticatedOrReadOnly"""

    def test_anonymous_can_read(self):
        """المستخدم غير المصادق عليه يستطيع القراءة"""
        from api.permissions import IsAuthenticatedOrReadOnly

        perm = IsAuthenticatedOrReadOnly()
        request = MagicMock()
        request.method = 'GET'
        view = MagicMock()
        assert perm.has_permission(request, view) is True

    def test_anonymous_cannot_write(self):
        """المستخدم غير المصادق عليه لا يستطيع الكتابة"""
        from api.permissions import IsAuthenticatedOrReadOnly

        perm = IsAuthenticatedOrReadOnly()
        request = MagicMock()
        request.method = 'POST'
        request.user = MagicMock(is_authenticated=False)
        view = MagicMock()
        assert perm.has_permission(request, view) is False

    def test_authenticated_can_write(self):
        """المستخدم المصادق عليه يستطيع الكتابة"""
        from api.permissions import IsAuthenticatedOrReadOnly

        perm = IsAuthenticatedOrReadOnly()
        request = MagicMock()
        request.method = 'POST'
        request.user = MagicMock(is_authenticated=True)
        view = MagicMock()
        assert perm.has_permission(request, view) is True


# ═══════════════════════════════════════════════════════════════
#  4.  ModulePermission
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestModulePermission:
    """اختبار صلاحية ModulePermission مع وحدات التحكم"""

    def test_staff_bypass(self, staff_user):
        """staff يتجاوز كل صلاحيات الوحدة"""
        from api.permissions import ModulePermission

        perm = ModulePermission()
        request = MagicMock()
        request.user = staff_user
        view = MagicMock()
        view.basename = 'accounts'
        view.action = 'list'
        assert perm.has_permission(request, view) is True

    def test_non_staff_allowed_when_resolver_returns_true(self):
        """مستخدم عادي مسموح له عندما يُرجع المحول True"""
        from api.permissions import ModulePermission

        user = MagicMock(is_staff=False)
        perm = ModulePermission()
        request = MagicMock()
        request.user = user
        view = MagicMock()
        view.basename = 'accounts'
        view.action = 'retrieve'
        with patch('access_control.resolver.has_permission', return_value=True, create=True):
            assert perm.has_permission(request, view) is True

    def test_non_staff_denied_when_resolver_returns_false(self):
        """مستخدم عادي مرفوض عندما يُرجع المحول False"""
        from api.permissions import ModulePermission

        user = MagicMock(is_staff=False)
        perm = ModulePermission()
        request = MagicMock()
        request.user = user
        view = MagicMock()
        view.basename = 'accounts'
        view.action = 'create'
        with patch('access_control.resolver.has_permission', return_value=False, create=True):
            assert perm.has_permission(request, view) is False

    def test_unknown_basename_denied(self):
        """basename غير معروف يُرفض"""
        from api.permissions import ModulePermission

        user = MagicMock(is_staff=False)
        perm = ModulePermission()
        request = MagicMock()
        request.user = user
        view = MagicMock()
        view.basename = 'unknown-module'
        view.action = 'list'
        with patch('access_control.resolver.has_permission', return_value=True, create=True):
            assert perm.has_permission(request, view) is False

    def test_action_mapping(self):
        """��스트 action map يُحوّل create إلى add و update إلى edit"""
        from api.permissions import ModulePermission

        perm = ModulePermission()
        assert perm.ACTION_MAP['list'] == 'view'
        assert perm.ACTION_MAP['create'] == 'add'
        assert perm.ACTION_MAP['update'] == 'edit'
        assert perm.ACTION_MAP['destroy'] == 'delete'

    def test_module_map_contains_known_modules(self):
        """الخريطة تحتوي الوحدات المعروفة"""
        from api.permissions import ModulePermission

        perm = ModulePermission()
        for key in ('accounts', 'suppliers', 'customers', 'products', 'employees', 'banks'):
            assert key in perm.MODULE_MAP


# ═══════════════════════════════════════════════════════════════
#  5.  UserViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserViewSet:
    """اختبار UserViewSet"""

    def test_list_users(self, auth_api_client, admin_user):
        """عرض قائمة المستخدمين"""
        resp = auth_api_client.get('/api/v1/users')
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)

    def test_retrieve_user(self, auth_api_client, admin_user):
        """عرض مستخدم واحد"""
        resp = auth_api_client.get(f'/api/v1/users/{admin_user.pk}')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['username'] == 'admin'

    def test_read_only_viewset(self, auth_api_client):
        """ViewSet للقراءة فقط - لا يسمح بالإنشاء"""
        resp = auth_api_client.post('/api/v1/users', {'username': 'new'})
        assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_search_users(self, auth_api_client, admin_user):
        """بحث المستخدمين"""
        resp = auth_api_client.get('/api/v1/users', {'search': 'admin'})
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════
#  6.  DepartmentViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDepartmentViewSet:
    """اختبار DepartmentViewSet"""

    def test_list_departments(self, auth_api_client):
        """عرض قائمة الأقسام"""
        resp = auth_api_client.get('/api/v1/departments')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_department(self, auth_api_client):
        """إنشاء قسم جديد"""
        resp = auth_api_client.post('/api/v1/departments', {'name': 'المحاسبة'})
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['name'] == 'المحاسبة'

    def test_update_department(self, auth_api_client):
        """تحديث قسم"""
        from hr.models import Department

        dept = Department.objects.create(name='(IT)')
        resp = auth_api_client.patch(f'/api/v1/departments/{dept.pk}', {'name': 'تقنية المعلومات'})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['name'] == 'تقنية المعلومات'

    def test_delete_department(self, auth_api_client):
        """حذف قسم"""
        from hr.models import Department

        dept = Department.objects.create(name='حذف')
        resp = auth_api_client.delete(f'/api/v1/departments/{dept.pk}')
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_search_departments(self, auth_api_client):
        """بحث في الأقسام"""
        from hr.models import Department

        Department.objects.create(name='قسم المبيعات')
        resp = auth_api_client.get('/api/v1/departments', {'search': 'مبيعات'})
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_active_departments(self, auth_api_client):
        """تصفية الأقسام النشطة"""
        from hr.models import Department

        Department.objects.create(name='نشيط', is_active=True)
        Department.objects.create(name='غير نشيط', is_active=False)
        resp = auth_api_client.get('/api/v1/departments', {'is_active': True})
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════
#  7.  CurrencyViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCurrencyViewSet:
    """اختبار CurrencyViewSet"""

    def test_list_currencies(self, auth_api_client):
        """عرض قائمة العملات"""
        resp = auth_api_client.get('/api/v1/currencies')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_currency(self, auth_api_client):
        """عملة جديدة"""
        resp = auth_api_client.post('/api/v1/currencies', {
            'code': 'EGP',
            'name': 'جنيه مصري',
            'symbol': 'ج.م',
        })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_search_currencies(self, auth_api_client):
        """بحث العملات"""
        from currency.models import Currency

        Currency.objects.create(code='USD', name='دولار أمريكي', symbol='$')
        resp = auth_api_client.get('/api/v1/currencies', {'search': 'دولار'})
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════
#  8.  AccountTypeViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAccountTypeViewSet:
    """اختبار AccountTypeViewSet"""

    def test_list_account_types(self, auth_api_client):
        """عرض قائمة أنواع الحسابات"""
        resp = auth_api_client.get('/api/v1/account-types')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_account_type(self, auth_api_client):
        """إنشاء نوع حساب"""
        resp = auth_api_client.post('/api/v1/account-types', {
            'name': 'أصول',
            'code': 'assets',
            'account_type': 'asset',
        })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_ordering_account_types(self, auth_api_client):
        """ترتيب أنواع الحسابات"""
        from accounts.models import AccountType

        AccountType.objects.create(name='ميزان العمليات', code='trial', account_type='trial')
        resp = auth_api_client.get('/api/v1/account-types', {'ordering': 'code'})
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════
#  9.  WarehouseViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWarehouseViewSet:
    """اختبار WarehouseViewSet"""

    def test_crud_warehouse(self, auth_api_client):
        """إنشاء وعرض وتحديث وحذف مخزن"""
        resp = auth_api_client.post('/api/v1/warehouses', {
            'name': 'المخزن الرئيسي',
            'code': 'WH-001',
        })
        assert resp.status_code == status.HTTP_201_CREATED
        pk = resp.data['id']

        resp = auth_api_client.get(f'/api/v1/warehouses/{pk}')
        assert resp.status_code == status.HTTP_200_OK

        resp = auth_api_client.patch(f'/api/v1/warehouses/{pk}', {'name': 'مخزن Updated'})
        assert resp.status_code == status.HTTP_200_OK

        resp = auth_api_client.delete(f'/api/v1/warehouses/{pk}')
        assert resp.status_code == status.HTTP_204_NO_CONTENT


# ═══════════════════════════════════════════════════════════════
#  10.  DocumentTypeViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDocumentTypeViewSet:
    """اختبار DocumentTypeViewSet"""

    def test_list_document_types(self, auth_api_client):
        """عرض قائمة أنواع المستندات"""
        resp = auth_api_client.get('/api/v1/document-types')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_document_type(self, auth_api_client):
        """إنشاء نوع مستند"""
        resp = auth_api_client.post('/api/v1/document-types', {
            'name': 'عقد',
            'code': 'CONTRACT',
            'prefix': 'CON',
        })
        assert resp.status_code == status.HTTP_201_CREATED


# ═══════════════════════════════════════════════════════════════
#  11.  api_login endpoint
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestApiLogin:
    """اختبار نقطة دخول API"""

    def test_login_valid_credentials(self, fresh_client, admin_user):
        """تسجيل دخول بنجاح"""
        resp = fresh_client.post('/api/v1/auth/login/', {
            'username': 'admin',
            'password': 'admin123',
        }, format='json')
        assert resp.status_code == status.HTTP_200_OK
        assert 'token' in resp.data
        assert resp.data['is_superuser'] is True

    def test_login_invalid_credentials(self, fresh_client):
        """تسجيل دخول بكلمة مرور خاطئة"""
        resp = fresh_client.post('/api/v1/auth/login/', {
            'username': 'admin',
            'password': 'wrong',
        }, format='json')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in resp.data

    def test_login_nonexistent_user(self, fresh_client):
        """تسجيل دخول بمستخدم غير موجود"""
        resp = fresh_client.post('/api/v1/auth/login/', {
            'username': 'ghost',
            'password': 'ghost123',
        }, format='json')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════
#  12.  api_dashboard endpoint
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestApiDashboard:
    """اختبار نقطة ملخص لوحة التحكم"""

    def test_dashboard_requires_auth(self, fresh_client):
        """لوحة التحكم تتطلب مصادقة"""
        resp = fresh_client.get('/api/v1/dashboard/')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dashboard_returns_data(self, auth_api_client):
        """لوحة التحكم تُرجع بيانات"""
        resp = auth_api_client.get('/api/v1/dashboard/')
        assert resp.status_code == status.HTTP_200_OK
        assert 'sales_this_month' in resp.data
        assert 'purchases_this_month' in resp.data
        assert 'total_receivable' in resp.data
        assert 'total_payable' in resp.data
        assert 'recent_entries' in resp.data


# ═══════════════════════════════════════════════════════════════
#  13.  api_stock_summary endpoint
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestApiStockSummary:
    """اختبار نقطة ملخص المخزون"""

    def test_stock_summary_requires_auth(self, fresh_client):
        """ملخص المخزون يتطلب مصادقة"""
        resp = fresh_client.get('/api/v1/stock-summary/')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_stock_summary_returns_list(self, auth_api_client):
        """ملخص المخزون يُرجع قائمة"""
        resp = auth_api_client.get('/api/v1/stock-summary/')
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)


# ═══════════════════════════════════════════════════════════════
#  14.  Token Authentication
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTokenAuthentication:
    """اختبار مصادقة التوكن"""

    def test_valid_token(self, fresh_client, admin_user):
        """توكن صحيح يفتح الوصول"""
        token, _ = Token.objects.get_or_create(user=admin_user)
        fresh_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        resp = fresh_client.get('/api/v1/users')
        assert resp.status_code == status.HTTP_200_OK

    def test_invalid_token(self, fresh_client):
        """توكن خاطئ يُرفض"""
        fresh_client.credentials(HTTP_AUTHORIZATION='Token faketoken123456')
        resp = fresh_client.get('/api/v1/users')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_no_token(self, fresh_client, admin_user):
        """بدون توكن يُرفض"""
        resp = fresh_client.get('/api/v1/users')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════
#  15.  AccountViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAccountViewSet:
    """اختبار AccountViewSet"""

    def test_list_accounts(self, auth_api_client):
        """عرض قائمة الحسابات"""
        resp = auth_api_client.get('/api/v1/accounts')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_account(self, auth_api_client):
        """إنشاء حساب جديد"""
        from accounts.models import AccountType

        at = AccountType.objects.create(name='أصول', code='AST', account_type='asset')
        resp = auth_api_client.post('/api/v1/accounts', {
            'name': 'حساب نقد',
            'code': '1001',
            'account_type': at.pk,
        })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_search_accounts(self, auth_api_client):
        """بحث الحسابات"""
        from accounts.models import Account, AccountType

        at = AccountType.objects.create(name='بنوك', code='BNK', account_type='asset')
        Account.objects.create(name='حساب بنك', code='2001', account_type=at)
        resp = auth_api_client.get('/api/v1/accounts', {'search': 'بنك'})
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════
#  16.  ProductViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestProductViewSet:
    """اختبار ProductViewSet"""

    def test_list_products(self, auth_api_client):
        """عرض قائمة المنتجات"""
        resp = auth_api_client.get('/api/v1/products')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_product(self, auth_api_client):
        """إنشاء منتج"""
        from purchases.models import ProductCategory, UnitOfMeasure

        cat = ProductCategory.objects.create(name='إلكترونيات', code='ELEC')
        unit = UnitOfMeasure.objects.create(name='قطعة', code='PC', symbol='pc')
        resp = auth_api_client.post('/api/v1/products', {
            'name': 'لابتوب',
            'code': 'LAP-001',
            'category': cat.pk,
            'unit_of_measure': unit.pk,
            'selling_price': '25000.00',
            'cost_price': '20000.00',
        })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_search_products(self, auth_api_client):
        """بحث المنتجات"""
        from purchases.models import Product, ProductCategory, UnitOfMeasure

        cat = ProductCategory.objects.create(name='أطعمة', code='FD')
        unit = UnitOfMeasure.objects.create(name='كجم', code='KG', symbol='kg')
        Product.objects.create(name='أرز بسمتي', code='RICE-001', category=cat, unit_of_measure=unit,
                               selling_price=50, purchase_price=40, current_stock=100)
        resp = auth_api_client.get('/api/v1/products', {'search': 'أرز'})
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════
#  17.  SupplierViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSupplierViewSet:
    """اختبار SupplierViewSet"""

    def test_list_suppliers(self, auth_api_client):
        """عرض قائمة الموردين"""
        resp = auth_api_client.get('/api/v1/suppliers')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_supplier(self, auth_api_client):
        """إنشاء مورد"""
        from accounts.models import Account, AccountType

        at = AccountType.objects.create(name='موردون', code='SUP', account_type='liability')
        acc = Account.objects.create(name='موردون عام', code='3001', account_type=at)
        resp = auth_api_client.post('/api/v1/suppliers', {
            'name': 'شركة الأمل',
            'code': 'SUP-001',
            'account': acc.pk,
        })
        assert resp.status_code == status.HTTP_201_CREATED


# ═══════════════════════════════════════════════════════════════
#  18.  CustomerViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCustomerViewSet:
    """اختبار CustomerViewSet"""

    def test_list_customers(self, auth_api_client):
        """عرض قائمة العملاء"""
        resp = auth_api_client.get('/api/v1/customers')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_customer(self, auth_api_client):
        """إنشاء عميل"""
        from accounts.models import Account, AccountType

        at = AccountType.objects.create(name='عملاء', code='CUS', account_type='asset')
        acc = Account.objects.create(name='عملاء عام', code='4001', account_type=at)
        resp = auth_api_client.post('/api/v1/customers', {
            'name': 'عميل تجريبي',
            'code': 'CUS-001',
            'account': acc.pk,
        })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_search_customers(self, auth_api_client):
        """بحث العملاء"""
        from accounts.models import Account, AccountType
        from sales.models import Customer

        at = AccountType.objects.create(name='عملاء2', code='CUS2', account_type='asset')
        acc = Account.objects.create(name='عملاء2', code='4002', account_type=at)
        Customer.objects.create(name='أحمد', code='C01', account=acc)
        resp = auth_api_client.get('/api/v1/customers', {'search': 'أحمد'})
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════
#  19.  BankViewSet & SafeViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTreasuryViewSets:
    """اختبار ViewSets الخزينة"""

    def test_list_banks(self, auth_api_client):
        """عرض البنوك"""
        resp = auth_api_client.get('/api/v1/banks')
        assert resp.status_code == status.HTTP_200_OK

    def test_list_safes(self, auth_api_client):
        """عرض الخزائن"""
        resp = auth_api_client.get('/api/v1/safes')
        assert resp.status_code == status.HTTP_200_OK

    def test_create_bank(self, auth_api_client):
        """إنشاء بنك"""
        from accounts.models import Account, AccountType

        at = AccountType.objects.create(name='بنوك', code='BANK', account_type='asset')
        acc = Account.objects.create(name='بنك 示例', code='5001', account_type=at)
        resp = auth_api_client.post('/api/v1/banks', {
            'name': 'البنك الأهلي',
            'account': acc.pk,
            'account_number': '1234567890',
        })
        assert resp.status_code == status.HTTP_201_CREATED


# ═══════════════════════════════════════════════════════════════
#  20.  AuditLogViewSet (read-only)
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAuditLogViewSet:
    """اختبار AuditLogViewSet"""

    def test_list_audit_logs(self, auth_api_client):
        """عرض سجل التدقيق"""
        resp = auth_api_client.get('/api/v1/audit-logs')
        assert resp.status_code == status.HTTP_200_OK

    def test_audit_log_read_only(self, auth_api_client):
        """سجل التدقيق للقراءة فقط"""
        resp = auth_api_client.post('/api/v1/audit-logs', {'model_name': 'test'})
        assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# ═══════════════════════════════════════════════════════════════
#  21.  CostCenterViewSet
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCostCenterViewSet:
    """اختبار CostCenterViewSet"""

    def test_create_cost_center(self, auth_api_client):
        """إنشاء مركز تكلفة"""
        resp = auth_api_client.post('/api/v1/cost-centers', {
            'name': 'الإدارة',
            'code': 'CC-001',
        })
        assert resp.status_code == status.HTTP_201_CREATED

    def test_list_cost_centers(self, auth_api_client):
        """عرض مراكز التكلفة"""
        resp = auth_api_client.get('/api/v1/cost-centers')
        assert resp.status_code == status.HTTP_200_OK
