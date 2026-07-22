"""
طبقة الحسم الموحّدة للصلاحيات (Permission Resolution Layer).

مصدر الحقيقة الوحيد الذي يستدعيه كلٌّ من الديكوريتر والقوالب ولوحة الإدارة،
بحيث يتطابق ما يُعرض على المسؤول مع ما يُفرض فعلاً.

قواعد الحسم:
- المشرف (superuser) يتجاوز كل شيء.
- الرفض هو الافتراضي (Deny by default).
- الصلاحية الوظيفية = اتحاد منح الأدوار (OR)، ثم تُطبَّق استثناءات المستخدم.
- الحرمان الصريح (deny) — من دور أو من استثناء مستخدم — يتغلّب على أي منح.
"""

from datetime import date

from django.core.cache import cache

from .models import (
    RoleScreenPermission,
    UserAccountTypeScope,
    UserBranch,
    UserRoleAssignment,
    UserScreenPermission,
    UserWarehouse,
)

LEVELS = ('view', 'add', 'edit', 'delete', 'print', 'export')
_GLOBAL_VERSION_KEY = 'access_control:perm_version'
_CACHE_TTL = 300


def _global_version():
    ver = cache.get(_GLOBAL_VERSION_KEY)
    if ver is None:
        ver = 1
        cache.set(_GLOBAL_VERSION_KEY, ver, None)
    return ver


def bump_global_version():
    """يُبطل كاش الصلاحيات لكل المستخدمين ذرّياً."""
    try:
        cache.incr(_GLOBAL_VERSION_KEY)
    except ValueError:
        cache.set(_GLOBAL_VERSION_KEY, _global_version() + 1, None)


def _user_cache_key(user_id):
    return f'access_control:perms:v{_global_version()}:{user_id}'


def invalidate_user(user_id):
    """يحذف كاش مستخدم محدّد فور تعديل صلاحياته."""
    cache.delete(_user_cache_key(user_id))


class ResolvedPermissions:
    """بنية الصلاحيات الفعّالة المُجمّعة لمستخدم واحد."""

    def __init__(self, data):
        self.is_superuser = data['is_superuser']
        self.screens = data['screens']
        self.branches = data['branches']
        self.warehouses = data['warehouses']
        self.account_types = data['account_types']
        self.can_view_prices = data['can_view_prices']
        self.view_all_branches = data['view_all_branches']
        self.view_all_warehouses = data['view_all_warehouses']
        self.has_roles = data.get('has_roles', False)

    def can(self, screen_code, level='view'):
        if self.is_superuser:
            return True
        return bool(self.screens.get(screen_code, {}).get(level, False))

    def branch_ids(self):
        return self.branches

    def warehouse_op(self, warehouse_id, op):
        if self.is_superuser or self.view_all_warehouses:
            return True
        return bool(self.warehouses.get(str(warehouse_id), {}).get(op, False))

    def account_type_op(self, account_type_id, op='view'):
        if self.is_superuser:
            return True
        return bool(self.account_types.get(str(account_type_id), {}).get(op, False))

    def as_dict(self):
        return {
            'is_superuser': self.is_superuser,
            'screens': self.screens,
            'branches': self.branches,
            'warehouses': self.warehouses,
            'account_types': self.account_types,
            'can_view_prices': self.can_view_prices,
            'view_all_branches': self.view_all_branches,
            'view_all_warehouses': self.view_all_warehouses,
            'has_roles': self.has_roles,
        }


def _active_role_ids(user):
    today = date.today()
    qs = UserRoleAssignment.objects.filter(user=user, role__is_active=True)
    ids = []
    for a in qs.values('role_id', 'valid_until'):
        if a['valid_until'] and a['valid_until'] < today:
            continue
        ids.append(a['role_id'])
    return ids


def _resolve_screens(user, role_ids):
    """يُرجع {screen_code: {level: bool}} بعد دمج الأدوار واستثناءات المستخدم."""
    allow = {}
    deny = {}

    def _apply(store, screen_code, flags):
        bucket = store.setdefault(screen_code, {})
        for lvl in LEVELS:
            if flags[lvl]:
                bucket[lvl] = True

    if role_ids:
        rperms = RoleScreenPermission.objects.filter(role_id__in=role_ids).select_related('screen')
        for rp in rperms:
            code = rp.screen.code
            target = deny if rp.grant_type == 'deny' else allow
            _apply(target, code, rp.levels_dict())

    uperms = UserScreenPermission.objects.filter(user=user).select_related('screen')
    for up in uperms:
        code = up.screen.code
        target = deny if up.grant_type == 'deny' else allow
        _apply(target, code, up.levels_dict())

    effective = {}
    for code, flags in allow.items():
        eff = {}
        for lvl in LEVELS:
            eff[lvl] = bool(flags.get(lvl)) and not deny.get(code, {}).get(lvl, False)
        if any(eff.values()):
            effective[code] = eff
    return effective


def _resolve_scopes(user, profile):
    branches = [str(b) for b in UserBranch.objects.filter(user=user).values_list('branch_id', flat=True)]
    if profile and profile.branch_id and str(profile.branch_id) not in branches:
        branches.append(str(profile.branch_id))

    warehouses = {}
    for w in UserWarehouse.objects.filter(user=user):
        warehouses[str(w.warehouse_id)] = {
            'receive': w.can_receive,
            'issue': w.can_issue,
            'count': w.can_count,
            'transfer': w.can_transfer,
        }

    account_types = {}
    for a in UserAccountTypeScope.objects.filter(user=user):
        account_types[str(a.account_type_id)] = {'view': a.can_view, 'transact': a.can_transact}

    return branches, warehouses, account_types


def _compute(user):
    from common.permissions import get_user_profile

    profile = get_user_profile(user)
    view_all_branches = bool(profile and profile.view_all_branches)
    view_all_warehouses = bool(profile and profile.view_all_warehouses)
    can_view_prices = bool(profile.can_view_prices) if profile else True

    if user.is_superuser:
        return {
            'is_superuser': True,
            'screens': {},
            'branches': [],
            'warehouses': {},
            'account_types': {},
            'can_view_prices': True,
            'view_all_branches': True,
            'view_all_warehouses': True,
            'has_roles': True,
        }

    role_ids = _active_role_ids(user)
    branches, warehouses, account_types = _resolve_scopes(user, profile)
    return {
        'is_superuser': False,
        'screens': _resolve_screens(user, role_ids),
        'branches': branches,
        'warehouses': warehouses,
        'account_types': account_types,
        'can_view_prices': can_view_prices,
        'view_all_branches': view_all_branches,
        'view_all_warehouses': view_all_warehouses,
        'has_roles': bool(role_ids),
    }


def resolve(user, use_cache=True):
    """يُرجع ResolvedPermissions لمستخدم، مع تخزين مؤقت وإبطال آمن."""
    if not user or not getattr(user, 'is_authenticated', False):
        return ResolvedPermissions(
            {
                'is_superuser': False,
                'screens': {},
                'branches': [],
                'warehouses': {},
                'account_types': {},
                'can_view_prices': False,
                'view_all_branches': False,
                'view_all_warehouses': False,
                'has_roles': False,
            }
        )

    if not use_cache:
        return ResolvedPermissions(_compute(user))

    key = _user_cache_key(user.pk)
    data = cache.get(key)
    if data is None:
        data = _compute(user)
        cache.set(key, data, _CACHE_TTL)
    return ResolvedPermissions(data)
