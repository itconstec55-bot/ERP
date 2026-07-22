from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.test import RequestFactory

from access_control.models import (
    GRANT_TYPES,
    Role,
    RoleScreenPermission,
    Screen,
    ScreenAccessMixin,
    UserAccountTypeScope,
    UserBranch,
    UserRoleAssignment,
    UserScreenPermission,
    UserWarehouse,
)
from access_control.resolver import (
    LEVELS,
    ResolvedPermissions,
    _active_role_ids,
    _resolve_screens,
    bump_global_version,
    invalidate_user,
    resolve,
)
from common.models import UserProfile
from common.permissions import can_access_branch, can_view_prices, get_user_profile, screen_permission_required

# ─── fixtures ───


@pytest.fixture
def screen_obj(db):
    return Screen.objects.create(code='sales.invoice', name='فاتورة مبيعات', module='sales', order=1)


@pytest.fixture
def role_obj(db):
    return Role.objects.create(name='محاسب', code='accountant')


@pytest.fixture
def simple_user(db):
    return User.objects.create_user('test_u', 'test_u@test.com', 'pass1234')


# ═══════════════════════════════════════════════════════════════
#  1.  Role model
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRoleModel:
    """اختبار نموذج الدور"""

    def test_create_role(self):
        """إنشاء دور جديد"""
        role = Role.objects.create(name='مدير', code='manager')
        assert role.pk is not None
        assert role.name == 'مدير'
        assert role.is_active is True
        assert role.is_system is False

    def test_role_str(self):
        """تمثيل الدور النصي"""
        role = Role.objects.create(name='مشرف', code='supervisor')
        assert str(role) == 'مشرف'

    def test_system_role_flag(self):
        """الدور النظامي"""
        role = Role.objects.create(name='نظامي', code='sys', is_system=True)
        assert role.is_system is True

    def test_role_unique_code(self, role_obj):
        """كود الدور فريد"""
        with pytest.raises(Exception):  # noqa: B017
            Role.objects.create(name='(another)', code='accountant')

    def test_role_ordering(self):
        """ترتيب الأدوار بالاسم"""
        r2 = Role.objects.create(name='ب', code='b')
        r1 = Role.objects.create(name='أ', code='a')
        roles = list(Role.objects.all())
        assert roles[0] == r1
        assert roles[1] == r2


# ═══════════════════════════════════════════════════════════════
#  2.  Screen model
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestScreenModel:
    """اختبار نموذج الشاشة"""

    def test_create_screen(self, screen_obj):
        """إنشاء شاشة"""
        assert screen_obj.pk is not None
        assert screen_obj.code == 'sales.invoice'

    def test_screen_str(self, screen_obj):
        """تمثيل الشاشة النصي"""
        result = str(screen_obj)
        assert 'فاتورة مبيعات' in result
        assert 'sales.invoice' in result

    def test_screen_unique_code(self, screen_obj):
        """كود الشاشة فريد"""
        with pytest.raises(Exception):  # noqa: B017
            Screen.objects.create(code='sales.invoice', name='(dup)')


# ═══════════════════════════════════════════════════════════════
#  3.  RoleScreenPermission model
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRoleScreenPermission:
    """اختبار صلاحيات الدور على الشاشة"""

    def test_create_permission(self, role_obj, screen_obj):
        """إنشاء صلاحية دور على شاشة"""
        perm = RoleScreenPermission.objects.create(
            role=role_obj,
            screen=screen_obj,
            can_view=True,
            can_add=True,
            can_edit=False,
            can_delete=False,
            can_print=True,
            can_export=False,
        )
        assert perm.pk is not None
        assert perm.grant_type == 'allow'

    def test_levels_dict(self, role_obj, screen_obj):
        """dict المستويات"""
        perm = RoleScreenPermission.objects.create(
            role=role_obj, screen=screen_obj, can_view=True, can_add=True, can_print=True,
        )
        d = perm.levels_dict()
        assert d['view'] is True
        assert d['add'] is True
        assert d['edit'] is False
        assert d['delete'] is False
        assert d['print'] is True
        assert d['export'] is False

    def test_deny_grant_type(self, role_obj, screen_obj):
        """نوع المنح: حرمان"""
        perm = RoleScreenPermission.objects.create(
            role=role_obj, screen=screen_obj, grant_type='deny', can_view=True,
        )
        assert perm.grant_type == 'deny'

    def test_str(self, role_obj, screen_obj):
        """تمثيل صلاحية الدور النصي"""
        perm = RoleScreenPermission.objects.create(role=role_obj, screen=screen_obj)
        assert str(perm)  # should not raise


# ═══════════════════════════════════════════════════════════════
#  4.  UserScreenPermission model
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserScreenPermission:
    """اختبار استثناء صلاحيات المستخدم"""

    def test_create_user_permission(self, simple_user, screen_obj):
        """إنشاء استثناء صلاحية مستخدم"""
        up = UserScreenPermission.objects.create(
            user=simple_user, screen=screen_obj, can_view=True, can_edit=True,
        )
        assert up.pk is not None
        assert up.can_view is True
        assert up.can_edit is True
        assert up.can_delete is False

    def test_user_permission_overrides_role(self, simple_user, role_obj, screen_obj):
        """استثناء المستخدم يتغلّب على الدور"""
        RoleScreenPermission.objects.create(
            role=role_obj, screen=screen_obj, can_view=True, can_edit=True,
        )
        UserScreenPermission.objects.create(
            user=simple_user, screen=screen_obj, grant_type='deny', can_view=True,
        )
        UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is False

    def test_default_permissions(self, simple_user, screen_obj):
        """الصلاحيات الافتراضية = false"""
        up = UserScreenPermission.objects.create(user=simple_user, screen=screen_obj)
        assert up.can_view is False
        assert up.can_add is False
        assert up.can_export is False


# ═══════════════════════════════════════════════════════════════
#  5.  UserRoleAssignment model
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserRoleAssignment:
    """اختبار إسناد الأدوار"""

    def test_assign_role(self, simple_user, role_obj):
        """إسناد دور لمستخدم"""
        assignment = UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        assert assignment.pk is not None

    def test_assignment_str(self, simple_user, role_obj):
        """تمثيل الإسناد النصي"""
        assignment = UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        result = str(assignment)
        assert 'test_u' in result

    def test_expired_assignment_ignored(self, simple_user, role_obj):
        """الإسناد منتهي الصلاحية يُتجاهل"""
        UserRoleAssignment.objects.create(
            user=simple_user, role=role_obj, valid_until=date.today() - timedelta(days=1),
        )
        assert _active_role_ids(simple_user) == []

    def test_valid_assignment_included(self, simple_user, role_obj):
        """الإسناد الساري يُحتسب"""
        UserRoleAssignment.objects.create(
            user=simple_user, role=role_obj, valid_until=date.today() + timedelta(days=30),
        )
        assert role_obj.pk in _active_role_ids(simple_user)

    def test_unique_constraint(self, simple_user, role_obj):
        """إسناد مزدوج لنفس الدور يُرفض"""
        UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        with pytest.raises(Exception):  # noqa: B017
            UserRoleAssignment.objects.create(user=simple_user, role=role_obj)


# ═══════════════════════════════════════════════════════════════
#  6.  resolve() – superuser
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestResolverSuperuser:
    """اختبار محول الصلاحيات – المشرف"""

    def test_superuser_always_allowed(self, admin_user):
        """المشرف يتجاوز كل صلاحيات الشاشة"""
        perms = resolve(admin_user, use_cache=False)
        assert perms.is_superuser is True
        assert perms.can('any.screen', 'delete') is True

    def test_superuser_view_all_branches(self, admin_user):
        """المشرف يرى كل الفروع"""
        perms = resolve(admin_user, use_cache=False)
        assert perms.view_all_branches is True

    def test_superuser_view_all_warehouses(self, admin_user):
        """المشرف يرى كل المخازن"""
        perms = resolve(admin_user, use_cache=False)
        assert perms.view_all_warehouses is True

    def test_superuser_can_view_prices(self, admin_user):
        """المشرف يرى الأسعار"""
        perms = resolve(admin_user, use_cache=False)
        assert perms.can_view_prices is True


# ═══════════════════════════════════════════════════════════════
#  7.  resolve() – unauthenticated / anonymous
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestResolverAnonymous:
    """اختبار محول الصلاحيات – مستخدم غير مصادق"""

    def test_anonymous_user(self):
        """مستخدم غير مصادق = لا صلاحيات"""
        anon = MagicMock()
        anon.is_authenticated = False
        perms = resolve(anon)
        assert perms.is_superuser is False
        assert perms.can('sales.invoice', 'view') is False

    def test_none_user(self):
        """مستخدم None = لا صلاحيات"""
        perms = resolve(None)
        assert perms.is_superuser is False
        assert perms.can('sales.invoice', 'view') is False


# ═══════════════════════════════════════════════════════════════
#  8.  resolve() – regular user with roles
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestResolverRegularUser:
    """اختبار محول الصلاحيات – مستخدم عادي بأدوار"""

    def test_user_with_role_can_see(self, simple_user, role_obj, screen_obj):
        """مستخدم بدور يملك صلاحية مشاهدة"""
        RoleScreenPermission.objects.create(
            role=role_obj, screen=screen_obj, can_view=True,
        )
        UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is True

    def test_user_without_role_cannot_see(self, simple_user, screen_obj):
        """مستخدم بدون دور لا يملك صلاحية"""
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is False

    def test_user_with_edit_via_role(self, simple_user, role_obj, screen_obj):
        """مستخدم بدور يملك صلاحية تعديل"""
        RoleScreenPermission.objects.create(
            role=role_obj, screen=screen_obj, can_edit=True,
        )
        UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'edit') is True
        assert perms.can('sales.invoice', 'delete') is False

    def test_user_can_via_user_screen_perm(self, simple_user, screen_obj):
        """مستخدم يملك صلاحية شاشة مباشرة"""
        UserScreenPermission.objects.create(
            user=simple_user, screen=screen_obj, can_view=True, can_add=True,
        )
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is True
        assert perms.can('sales.invoice', 'add') is True

    def test_unknown_screen_returns_false(self, simple_user):
        """شاشة غير معروفة = false"""
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('nonexistent.screen', 'view') is False

    def test_has_roles_flag(self, simple_user, role_obj, screen_obj):
        """علامة has_roles تُفعّل عند وجود أدوار"""
        RoleScreenPermission.objects.create(role=role_obj, screen=screen_obj, can_view=True)
        UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        perms = resolve(simple_user, use_cache=False)
        assert perms.has_roles is True


# ═══════════════════════════════════════════════════════════════
#  9.  resolve() – deny grant type
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestResolverDeny:
    """اختبار تغلّب الحرمان الصريح"""

    def test_role_deny_overrides_allow(self, simple_user, screen_obj):
        """حرمان الدور يتغلّب على منحه"""
        r_allow = Role.objects.create(name='(R-Allow)', code='r_allow')
        r_deny = Role.objects.create(name='(R-Deny)', code='r_deny')
        RoleScreenPermission.objects.create(
            role=r_allow, screen=screen_obj, can_view=True, can_edit=True,
        )
        RoleScreenPermission.objects.create(
            role=r_deny, screen=screen_obj, grant_type='deny', can_edit=True,
        )
        UserRoleAssignment.objects.create(user=simple_user, role=r_allow)
        UserRoleAssignment.objects.create(user=simple_user, role=r_deny)
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is True
        assert perms.can('sales.invoice', 'edit') is False

    def test_user_deny_overrides_role_allow(self, simple_user, screen_obj):
        """حرمان المستخدم يتغلّب على منح الدور"""
        role = Role.objects.create(name='(R-DenyTest)', code='deny_role')
        RoleScreenPermission.objects.create(
            role=role, screen=screen_obj, can_view=True,
        )
        UserScreenPermission.objects.create(
            user=simple_user, screen=screen_obj, grant_type='deny', can_view=True,
        )
        UserRoleAssignment.objects.create(user=simple_user, role=role)
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is False


# ═══════════════════════════════════════════════════════════════
#  10.  ResolvedPermissions.can()
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestResolvedPermissionsCan:
    """اختبار طريقة can() في ResolvedPermissions"""

    def test_can_returns_false_for_missing_screen(self):
        """can تُرجع False لشاشة غير موجودة"""
        rp = ResolvedPermissions({
            'is_superuser': False,
            'screens': {},
            'branches': [],
            'warehouses': {},
            'account_types': {},
            'can_view_prices': False,
            'view_all_branches': False,
            'view_all_warehouses': False,
        })
        assert rp.can('anything', 'view') is False

    def test_can_with_screen_data(self):
        """can تُرجع True عند وجود صلاحية"""
        rp = ResolvedPermissions({
            'is_superuser': False,
            'screens': {'sales.invoice': {'view': True, 'edit': False}},
            'branches': [],
            'warehouses': {},
            'account_types': {},
            'can_view_prices': False,
            'view_all_branches': False,
            'view_all_warehouses': False,
        })
        assert rp.can('sales.invoice', 'view') is True
        assert rp.can('sales.invoice', 'edit') is False

    def test_as_dict(self):
        """as_dict يُرجع dict كامل"""
        data = {
            'is_superuser': False, 'screens': {}, 'branches': [],
            'warehouses': {}, 'account_types': {}, 'can_view_prices': False,
            'view_all_branches': False, 'view_all_warehouses': False,
        }
        rp = ResolvedPermissions(data)
        d = rp.as_dict()
        assert d['is_superuser'] is False
        assert 'screens' in d
        assert 'branches' in d


# ═══════════════════════════════════════════════════════════════
#  11.  Permission caching
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPermissionCaching:
    """اختبار التخزين المؤقت للصلاحيات"""

    def test_resolve_uses_cache(self, simple_user, role_obj, screen_obj):
        """الاستدعاء الثاني يأخذ من الكاش"""
        RoleScreenPermission.objects.create(role=role_obj, screen=screen_obj, can_view=True)
        UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        p1 = resolve(simple_user, use_cache=True)
        p2 = resolve(simple_user, use_cache=True)
        assert p1.can('sales.invoice', 'view') == p2.can('sales.invoice', 'view')

    def test_bump_global_version_invalidates(self, simple_user, role_obj, screen_obj):
        """ bumped الإصدار يُبطل الكاش"""
        RoleScreenPermission.objects.create(role=role_obj, screen=screen_obj, can_view=True)
        UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        resolve(simple_user, use_cache=True)
        old_ver = cache.get('access_control:perm_version', 1)
        bump_global_version()
        new_ver = cache.get('access_control:perm_version', 1)
        assert new_ver > old_ver

    def test_invalidate_user(self, simple_user):
        """حذف كاش مستخدم محدد"""
        invalidate_user(simple_user.pk)
        from access_control.resolver import _user_cache_key

        assert cache.get(_user_cache_key(simple_user.pk)) is None


# ═══════════════════════════════════════════════════════════════
#  12.  screen_permission_required decorator
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestScreenPermissionRequiredDecorator:
    """اختبار ديكوريتر screen_permission_required"""

    def _make_view(self):
        def my_view(request):
            return HttpResponse('OK')
        return my_view

    def test_unauthenticated_redirects_to_login(self):
        """غير مصادق عليه → توجيه لصفحة الدخول"""
        decorated = screen_permission_required('sales.invoice', 'view')(self._make_view())
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = MagicMock(is_authenticated=False)
        resp = decorated(request)
        assert isinstance(resp, HttpResponseRedirect)

    def test_superuser_passes(self, admin_user):
        """المشرف يتجاوز"""
        decorated = screen_permission_required('sales.invoice', 'view')(self._make_view())
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = admin_user
        resp = decorated(request)
        assert resp.status_code == 200
        assert resp.content == b'OK'

    def test_user_with_permission_passes(self, simple_user, role_obj, screen_obj):
        """مستخدم بصلاحية يمر"""
        RoleScreenPermission.objects.create(role=role_obj, screen=screen_obj, can_view=True)
        UserRoleAssignment.objects.create(user=simple_user, role=role_obj)
        decorated = screen_permission_required('sales.invoice', 'view')(self._make_view())
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = simple_user
        resp = decorated(request)
        assert resp.status_code == 200

    def test_user_without_permission_redirects(self, db):
        """مستخدم بدون صلاحية → توجيه للوحة التحكم"""
        no_perm_user = User.objects.create_user('noperm', 'noperm@test.com', 'pass1234')
        invalidate_user(no_perm_user.pk)
        decorated = screen_permission_required('sales.invoice', 'view')(self._make_view())
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = no_perm_user
        msg_storage = MagicMock()
        request._messages = msg_storage
        resp = decorated(request)
        assert isinstance(resp, HttpResponseRedirect)


# ═══════════════════════════════════════════════════════════════
#  13.  seed_access_control command
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSeedAccessControl:
    """اختبار أمر زراعة الصلاحيات الأولية"""

    def test_seed_creates_screens(self):
        """الأمر يُنشئ الشاشات"""
        call_command('seed_access_control')
        assert Screen.objects.count() > 0

    def test_seed_creates_roles(self):
        """الأمر يُنشئ الأدوار"""
        call_command('seed_access_control')
        assert Role.objects.filter(is_system=True).count() > 0

    def test_seed_creates_role_permissions(self):
        """الأمر يُنشئ صلاحيات الأدوار"""
        call_command('seed_access_control')
        assert RoleScreenPermission.objects.count() > 0

    def test_seed_idempotent(self):
        """الأمر قابل للتشغيل المتكرر"""
        call_command('seed_access_control')
        n1 = Screen.objects.count()
        r1 = Role.objects.count()
        call_command('seed_access_control')
        assert Screen.objects.count() == n1
        assert Role.objects.count() == r1

    def test_admin_role_has_all_permissions(self):
        """دور المدير يملك كل الصلاحيات"""
        call_command('seed_access_control')
        admin_role = Role.objects.get(code='admin')
        perms = RoleScreenPermission.objects.filter(role=admin_role)
        for p in perms:
            assert p.can_view is True
            assert p.can_add is True


# ═══════════════════════════════════════════════════════════════
#  14.  get_user_profile
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetUserProfile:
    """اختبار دالة get_user_profile"""

    def test_none_user(self):
        """مستخدم None → None"""
        assert get_user_profile(None) is None

    def test_unauthenticated_user(self):
        """مستخدم غير مصادق → None"""
        anon = MagicMock()
        anon.is_authenticated = False
        assert get_user_profile(anon) is None

    def test_authenticated_user_with_profile(self, simple_user):
        """مستخدم مصادق عليه بملف → ملف"""
        UserProfile.objects.create(user=simple_user, account_type='viewer')
        assert get_user_profile(simple_user) is not None

    def test_authenticated_user_without_profile(self, simple_user):
        """مستخدم مصادق عليه بدون ملف → None"""
        assert get_user_profile(simple_user) is None


# ═══════════════════════════════════════════════════════════════
#  15.  can_access_branch
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCanAccessBranch:
    """اختبار دالة can_access_branch"""

    def test_none_branch_always_allowed(self, simple_user):
        """فرع None متاح للجميع"""
        assert can_access_branch(simple_user, None) is True

    def test_superuser_accesses_all(self, admin_user):
        """المشرف يصل لكل الفروع"""
        assert can_access_branch(admin_user, 999) is True

    def test_unauthenticated_denied(self):
        """غير مصادق → False"""
        anon = MagicMock()
        anon.is_authenticated = False
        assert can_access_branch(anon, 1) is False


# ═══════════════════════════════════════════════════════════════
#  16.  can_view_prices
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCanViewPrices:
    """اختبار دالة can_view_prices"""

    def test_superuser_can_view(self, admin_user):
        """المشرف يرى الأسعار"""
        assert can_view_prices(admin_user) is True

    def test_unauthenticated_cannot_view(self):
        """غير مصادق لا يرى الأسعار"""
        anon = MagicMock()
        anon.is_authenticated = False
        assert can_view_prices(anon) is False


# ═══════════════════════════════════════════════════════════════
#  17.  UserBranch / UserWarehouse / UserAccountTypeScope
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserScopeModels:
    """اختبار نماذج نطاق المستخدم"""

    def test_user_branch_str(self, simple_user):
        """تمثيل فرع المستخدم النصي"""
        from company.models import Company, CompanyBranch

        company = Company.objects.create(name='شركة تجريبية')
        branch = CompanyBranch.objects.create(name='فرع 1', company=company)
        ub = UserBranch.objects.create(user=simple_user, branch=branch)
        assert 'test_u' in str(ub)

    def test_user_warehouse_flags(self, simple_user):
        """أعلام المخزن"""
        from warehouses.models import Warehouse

        wh = Warehouse.objects.create(name='(WH)', code='W1')
        uw = UserWarehouse.objects.create(
            user=simple_user, warehouse=wh,
            can_receive=True, can_issue=True, can_count=False, can_transfer=False,
        )
        assert uw.can_receive is True
        assert uw.can_issue is True
        assert uw.can_count is False

    def test_user_account_type_scope(self, simple_user):
        """نطاق نوع الحساب"""
        from accounts.models import AccountType

        at = AccountType.objects.create(name='أصول', code='AST', account_type='asset')
        scope = UserAccountTypeScope.objects.create(user=simple_user, account_type=at, can_view=True, can_transact=False)
        assert scope.can_view is True
        assert scope.can_transact is False


# ═══════════════════════════════════════════════════════════════
#  18.  _resolve_screens function
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestResolveScreensFunction:
    """اختبار دالة _resolve_screens"""

    def test_empty_role_ids(self, simple_user):
        """أدوار فارغة → لا شاشات"""
        result = _resolve_screens(simple_user, [])
        assert result == {}

    def test_merging_multiple_roles(self, simple_user, screen_obj):
        """دمج صلاحيات أدوار متعددة"""
        r1 = Role.objects.create(name='(R1)', code='r1')
        r2 = Role.objects.create(name='(R2)', code='r2')
        RoleScreenPermission.objects.create(role=r1, screen=screen_obj, can_view=True)
        RoleScreenPermission.objects.create(role=r2, screen=screen_obj, can_add=True)
        result = _resolve_screens(simple_user, [r1.pk, r2.pk])
        assert result['sales.invoice']['view'] is True
        assert result['sales.invoice']['add'] is True
        assert result['sales.invoice']['edit'] is False


# ═══════════════════════════════════════════════════════════════
#  19.  GRANT_TYPES constant
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGrantTypes:
    """اختبار ثوابت أنواع المنح"""

    def test_grant_types_values(self):
        """أنواع المنح تحتوي allow و deny"""
        values = [g[0] for g in GRANT_TYPES]
        assert 'allow' in values
        assert 'deny' in values

    def test_levels_constant(self):
        """مستويات الوصول الستة"""
        assert len(LEVELS) == 6
        assert 'view' in LEVELS
        assert 'add' in LEVELS
        assert 'edit' in LEVELS
        assert 'delete' in LEVELS
        assert 'print' in LEVELS
        assert 'export' in LEVELS


# ═══════════════════════════════════════════════════════════════
#  20.  Multi-role merge + deny interaction
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMultiRoleDenyInteraction:
    """اختبار التفاعل بين أدوار متعددة وdenys"""

    def test_deny_role_beats_allow_role(self, simple_user, screen_obj):
        """دور بحرمان يتغلّب على دور بمنح"""
        r_allow = Role.objects.create(name='(AllowR)', code='ar')
        r_deny = Role.objects.create(name='(DenyR)', code='dr')
        RoleScreenPermission.objects.create(
            role=r_allow, screen=screen_obj, can_view=True, can_edit=True,
        )
        RoleScreenPermission.objects.create(
            role=r_deny, screen=screen_obj, grant_type='deny', can_view=True,
        )
        UserRoleAssignment.objects.create(user=simple_user, role=r_allow)
        UserRoleAssignment.objects.create(user=simple_user, role=r_deny)
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is False
        assert perms.can('sales.invoice', 'edit') is True


# ═══════════════════════════════════════════════════════════════
#  21.  expired vs valid role assignment in resolver
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestExpiredRoleAssignmentInResolver:
    """اختبار تجاهل الإسناد منتهي الصلاحية في المحول"""

    def test_expired_role_not_used(self, simple_user, role_obj, screen_obj):
        """إسناد منتهي لا يُحتسب في المحول"""
        RoleScreenPermission.objects.create(role=role_obj, screen=screen_obj, can_view=True)
        UserRoleAssignment.objects.create(
            user=simple_user, role=role_obj, valid_until=date.today() - timedelta(days=5),
        )
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is False

    def test_valid_role_used(self, simple_user, role_obj, screen_obj):
        """إسناد ساري يُحتسب"""
        RoleScreenPermission.objects.create(role=role_obj, screen=screen_obj, can_view=True)
        UserRoleAssignment.objects.create(
            user=simple_user, role=role_obj, valid_until=date.today() + timedelta(days=30),
        )
        perms = resolve(simple_user, use_cache=False)
        assert perms.can('sales.invoice', 'view') is True
