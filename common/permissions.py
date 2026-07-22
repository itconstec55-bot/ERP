from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def get_user_profile(user):
    """يُرجع ملف المستخدم إن وُجد."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return getattr(user, 'userprofile', None)


_ACTION_TO_LEVEL = {'view': 'view', 'add': 'add', 'change': 'edit', 'delete': 'delete'}


def _codename_to_screen(perm_codename):
    """يترجم كود صلاحية Django (app.action_model) إلى (screen_code, level) في النظام الجديد.
    الأفعال غير القياسية (approve/confirm/...) تُعامَل كـ edit. يُرجع (None, level) إذا
    تعذّرت المطابقة فيُترك الحسم على مستوى الموديل لديكوريتر الشاشة على العرض."""
    if '.' not in perm_codename:
        return None, 'view'
    from common.context_processors import SCREEN_TO_MODEL

    app_label, rest = perm_codename.split('.', 1)
    action, _, model = rest.partition('_')
    level = _ACTION_TO_LEVEL.get(action, 'edit')
    for code, (a, m) in SCREEN_TO_MODEL.items():
        if a == app_label and m == model:
            return code, level
    app_screens = [code for code, (a, _m) in SCREEN_TO_MODEL.items() if a == app_label]
    if len(app_screens) == 1:
        return app_screens[0], level
    return None, level


def has_object_permission(user, perm_codename, obj):
    """
    صلاحية على مستوى الكائن (تعتمد نظام الأدوار الجديد وحده):
    - المشرف يتجاوز كل شيء.
    - يجب أن يملك صلاحية الشاشة/المستوى المقابلة عبر طبقة الحسم الموحّدة.
    - يُمنع الوصول لسجل فرع مختلف ما لم يملك صلاحية مشاهدة كل الفروع.
    السجلات التي بلا فرع (branch=None) تكون متاحة للجميع.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    from access_control.resolver import resolve

    perms = resolve(user)
    screen_code, level = _codename_to_screen(perm_codename)
    if screen_code is not None and not perms.can(screen_code, level):
        return False
    profile = get_user_profile(user)
    if profile and profile.branch and not profile.view_all_branches:
        obj_branch = getattr(obj, 'branch', None)
        if obj_branch is not None and obj_branch != profile.branch:
            return False
    return True


def filter_by_branch(queryset, user):
    """تصفية queryset حسب فرع المستخدم (يُرجع الكل للمشرف/مشاهدة-الكل).
    السجلات بلا فرع (branch=None) تكون متاحة للجميع."""
    from django.db.models import Q

    if not user or not getattr(user, 'is_authenticated', False):
        return queryset
    if user.is_superuser:
        return queryset
    profile = get_user_profile(user)
    if profile and profile.branch and not profile.view_all_branches:
        return queryset.filter(Q(branch=profile.branch) | Q(branch__isnull=True))
    return queryset


def screen_permission_required(screen_code, level='view'):
    """
    ديكوريتر الصلاحيات القائم على الشاشات والمستويات الست.
    Usage: @screen_permission_required('sales.invoice', 'add')

    المصدر الوحيد للحسم هو نظام الأدوار (access_control.resolver): المشرف يتجاوز،
    وغيره يجب أن تكون لديه صلاحية الشاشة/المستوى صراحةً وإلا يُرفض ويُسجَّل.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            from access_control.resolver import resolve

            perms = resolve(request.user)
            if perms.can(screen_code, level):
                return view_func(request, *args, **kwargs)
            _log_access_denied(request, screen_code, level)
            messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
            return redirect('dashboard')

        return _wrapped

    return decorator


def _log_access_denied(request, screen_code, level):
    try:
        from audit.models import log_action

        log_action(request.user, 'access_denied', screen_code, object_repr=f'level={level}', request=request)
    except Exception:
        pass


def filter_by_user_branches(queryset, user, field='branch'):
    """تصفية queryset حسب الفروع المخوّلة للمستخدم عبر طبقة الحسم الموحّدة.
    السجلات بلا فرع تبقى متاحة للجميع."""
    from django.db.models import Q

    if not user or not getattr(user, 'is_authenticated', False):
        return queryset
    from access_control.resolver import resolve

    perms = resolve(user)
    if perms.is_superuser or perms.view_all_branches:
        return queryset
    branch_ids = perms.branch_ids()
    if not branch_ids:
        return queryset.filter(**{f'{field}__isnull': True})
    return queryset.filter(Q(**{f'{field}__in': branch_ids}) | Q(**{f'{field}__isnull': True}))


def filter_by_user_warehouses(queryset, user, field='warehouse'):
    """تصفية حركات/أرصدة المخازن حسب المخازن المخوّلة للمستخدم."""
    if not user or not getattr(user, 'is_authenticated', False):
        return queryset
    from access_control.resolver import resolve

    perms = resolve(user)
    if perms.is_superuser or perms.view_all_warehouses:
        return queryset
    ids = list(perms.warehouses.keys())
    return queryset.filter(**{f'{field}_id__in': ids})


def visible_warehouse_ids(user):
    """يُرجع None إذا كان يرى كل المخازن، وإلا قائمة معرّفات المخازن المخوّلة."""
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    from access_control.resolver import resolve

    perms = resolve(user)
    if perms.is_superuser or perms.view_all_warehouses:
        return None
    return list(perms.warehouses.keys())


def visible_account_type_ids(user):
    """يُرجع None إذا لم يُقيَّد المستخدم بأنواع حسابات، وإلا قائمة الأنواع المخوّلة للمشاهدة."""
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    from access_control.resolver import resolve

    perms = resolve(user)
    if perms.is_superuser:
        return None
    ids = [k for k, v in perms.account_types.items() if v.get('view')]
    if not ids:
        return None
    return ids


def can_access_branch(user, branch_id):
    """يتحقق من صلاحية المستخدم على فرع كائن محدد (None = متاح للجميع)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if branch_id is None:
        return True
    from access_control.resolver import resolve

    perms = resolve(user)
    if perms.is_superuser or perms.view_all_branches:
        return True
    return str(branch_id) in perms.branch_ids()


def can_account_type_operation(user, account_type_id, op='view'):
    """يتحقق من صلاحية المستخدم على نوع حساب (view/transact)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    from access_control.resolver import resolve

    return resolve(user).account_type_op(account_type_id, op)


def can_warehouse_operation(user, warehouse_id, operation):
    """يتحقق من صلاحية عملية مخزنية (receive/issue/count/transfer)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    from access_control.resolver import resolve

    return resolve(user).warehouse_op(warehouse_id, operation)


def can_view_prices(user):
    """يتحقق من صلاحية مشاهدة الأسعار والتكلفة."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    from access_control.resolver import resolve

    return resolve(user).can_view_prices


def object_permission_required(perm_codename, lookup_field='pk', model=None):
    """
    ديكوريتور لصلاحية على مستوى الكائن.
    يجلب الكائن ويفحص الصلاحية، وإلا يعيد توجيه لوحة التحكم برسالة خطأ.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            obj = None
            if model is not None and lookup_field in kwargs:
                from django.shortcuts import get_object_or_404

                obj = get_object_or_404(model, **{lookup_field: kwargs[lookup_field]})
            if not has_object_permission(request.user, perm_codename, obj):
                messages.error(request, 'ليس لديك صلاحية للوصول لهذا السجل')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
