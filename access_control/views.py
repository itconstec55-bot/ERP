from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from .models import (
    Role,
    RoleScreenPermission,
    Screen,
    UserAccountTypeScope,
    UserBranch,
    UserRoleAssignment,
    UserScreenPermission,
    UserWarehouse,
)
from .resolver import LEVELS, bump_global_version, invalidate_user, resolve

LEVEL_LABELS = {'view': 'مشاهدة', 'add': 'إضافة', 'edit': 'تعديل', 'delete': 'حذف', 'print': 'طباعة', 'export': 'تصدير'}


def _require_superuser(request):
    if not request.user.is_superuser:
        messages.error(request, 'هذه اللوحة متاحة لمدير النظام فقط')
        return False
    return True


@login_required
def permission_dashboard(request):
    """لوحة موحّدة: قائمة المستخدمين وأدوارهم ونطاقاتهم."""
    if not _require_superuser(request):
        return redirect('dashboard')
    users = (
        User.objects.all()
        .prefetch_related('role_assignments__role', 'allowed_branches', 'allowed_warehouses')
        .order_by('username')
    )
    return render(
        request,
        'access_control/dashboard.html',
        {'users': users, 'roles_count': Role.objects.count(), 'screens_count': Screen.objects.count()},
    )


@login_required
def user_permission_detail(request, pk):
    """مراجعة الصلاحيات الفعّالة لأي مستخدم في صفحة واحدة (من طبقة الحسم نفسها)."""
    if not _require_superuser(request):
        return redirect('dashboard')
    target = get_object_or_404(User, pk=pk)
    perms = resolve(target, use_cache=False)

    screens = Screen.objects.filter(is_active=True)
    screen_rows = []
    for screen in screens:
        eff = perms.screens.get(screen.code, {}) if not perms.is_superuser else {l: True for l in LEVELS}
        screen_rows.append({'screen': screen, 'cells': [bool(eff.get(l, False)) for l in LEVELS]})

    profile = getattr(target, 'userprofile', None)
    assignments = target.role_assignments.select_related('role').all()
    assigned_ids = [a.role_id for a in assignments]
    available_roles = Role.objects.filter(is_active=True).exclude(pk__in=assigned_ids).order_by('name')

    from accounts.models import AccountType
    from company.models import CompanyBranch
    from warehouses.models import Warehouse

    branch_ids = [b.branch_id for b in target.allowed_branches.all()]
    warehouse_ids = [w.warehouse_id for w in target.allowed_warehouses.all()]
    account_type_ids = [a.account_type_id for a in target.allowed_account_types.all()]
    available_branches = CompanyBranch.objects.filter(is_active=True).exclude(pk__in=branch_ids).order_by('name')
    available_warehouses = Warehouse.objects.filter(is_active=True).exclude(pk__in=warehouse_ids).order_by('name')
    available_account_types = AccountType.objects.exclude(pk__in=account_type_ids).order_by('name')

    exceptions = target.screen_permissions.select_related('screen').order_by('screen__module', 'screen__order')
    exception_rows = [
        {'perm': p, 'cells': [{'level': l, 'checked': getattr(p, f'can_{l}')} for l in LEVELS]} for p in exceptions
    ]
    all_screens = Screen.objects.filter(is_active=True).order_by('module', 'order', 'name')

    return render(
        request,
        'access_control/user_detail.html',
        {
            'target': target,
            'perms': perms,
            'profile': profile,
            'levels': LEVELS,
            'screen_rows': screen_rows,
            'assignments': assignments,
            'available_roles': available_roles,
            'roles': [a.role for a in assignments],
            'branches': target.allowed_branches.select_related('branch').all(),
            'warehouses': target.allowed_warehouses.select_related('warehouse').all(),
            'account_types': target.allowed_account_types.select_related('account_type').all(),
            'available_branches': available_branches,
            'available_warehouses': available_warehouses,
            'available_account_types': available_account_types,
            'exception_rows': exception_rows,
            'all_screens': all_screens,
            'level_headers': [(l, LEVEL_LABELS[l]) for l in LEVELS],
        },
    )


@login_required
def user_assign_role(request, pk):
    """إسناد دور لمستخدم من اللوحة نفسها."""
    if not _require_superuser(request):
        return redirect('dashboard')
    target = get_object_or_404(User, pk=pk)
    if request.method != 'POST':
        return redirect('access_control:user_detail', pk=target.pk)
    role_id = request.POST.get('role')
    role = Role.objects.filter(pk=role_id, is_active=True).first()
    if not role:
        messages.error(request, 'اختر مجموعة صحيحة')
        return redirect('access_control:user_detail', pk=target.pk)
    _, created = UserRoleAssignment.objects.get_or_create(user=target, role=role, defaults={'granted_by': request.user})
    invalidate_user(target.pk)
    messages.success(request, 'تم إسناد المجموعة' if created else 'المجموعة مُسنَدة بالفعل لهذا المستخدم')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_remove_role(request, pk, assignment_pk):
    """إزالة إسناد دور عن مستخدم."""
    if not _require_superuser(request):
        return redirect('dashboard')
    target = get_object_or_404(User, pk=pk)
    if request.method != 'POST':
        return redirect('access_control:user_detail', pk=target.pk)
    UserRoleAssignment.objects.filter(pk=assignment_pk, user=target).delete()
    invalidate_user(target.pk)
    messages.success(request, 'تم إزالة المجموعة')
    return redirect('access_control:user_detail', pk=target.pk)


def _target_or_redirect(request, pk):
    if not _require_superuser(request):
        return None, redirect('dashboard')
    target = get_object_or_404(User, pk=pk)
    if request.method != 'POST':
        return None, redirect('access_control:user_detail', pk=target.pk)
    return target, None


@login_required
def user_add_branch(request, pk):
    """إسناد فرع مخوّل للمستخدم."""
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    from company.models import CompanyBranch

    branch = CompanyBranch.objects.filter(pk=request.POST.get('branch'), is_active=True).first()
    if not branch:
        messages.error(request, 'اختر فرعاً صحيحاً')
        return redirect('access_control:user_detail', pk=target.pk)
    is_default = bool(request.POST.get('is_default'))
    if is_default:
        target.allowed_branches.update(is_default=False)
    UserBranch.objects.get_or_create(user=target, branch=branch, defaults={'is_default': is_default})
    invalidate_user(target.pk)
    messages.success(request, 'تم إسناد الفرع')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_remove_branch(request, pk, item_pk):
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    UserBranch.objects.filter(pk=item_pk, user=target).delete()
    invalidate_user(target.pk)
    messages.success(request, 'تم إزالة الفرع')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_add_warehouse(request, pk):
    """إسناد مخزن مخوّل للمستخدم مع أعلام العمليات."""
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    from warehouses.models import Warehouse

    warehouse = Warehouse.objects.filter(pk=request.POST.get('warehouse'), is_active=True).first()
    if not warehouse:
        messages.error(request, 'اختر مخزناً صحيحاً')
        return redirect('access_control:user_detail', pk=target.pk)
    UserWarehouse.objects.update_or_create(
        user=target,
        warehouse=warehouse,
        defaults={
            'can_receive': bool(request.POST.get('can_receive')),
            'can_issue': bool(request.POST.get('can_issue')),
            'can_count': bool(request.POST.get('can_count')),
            'can_transfer': bool(request.POST.get('can_transfer')),
        },
    )
    invalidate_user(target.pk)
    messages.success(request, 'تم إسناد المخزن')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_remove_warehouse(request, pk, item_pk):
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    UserWarehouse.objects.filter(pk=item_pk, user=target).delete()
    invalidate_user(target.pk)
    messages.success(request, 'تم إزالة المخزن')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_add_account_type(request, pk):
    """تقييد المستخدم على نوع حساب محاسبي."""
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    from accounts.models import AccountType

    account_type = AccountType.objects.filter(pk=request.POST.get('account_type')).first()
    if not account_type:
        messages.error(request, 'اختر نوع حساب صحيحاً')
        return redirect('access_control:user_detail', pk=target.pk)
    UserAccountTypeScope.objects.update_or_create(
        user=target,
        account_type=account_type,
        defaults={
            'can_view': bool(request.POST.get('can_view')),
            'can_transact': bool(request.POST.get('can_transact')),
        },
    )
    invalidate_user(target.pk)
    messages.success(request, 'تم إسناد نوع الحساب')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_remove_account_type(request, pk, item_pk):
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    UserAccountTypeScope.objects.filter(pk=item_pk, user=target).delete()
    invalidate_user(target.pk)
    messages.success(request, 'تم إزالة نوع الحساب')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_update_scope_flags(request, pk):
    """تحديث أعلام النطاق العامة في ملف المستخدم."""
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    from common.models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(user=target)
    profile.view_all_branches = bool(request.POST.get('view_all_branches'))
    profile.view_all_warehouses = bool(request.POST.get('view_all_warehouses'))
    profile.can_view_prices = bool(request.POST.get('can_view_prices'))
    profile.save(update_fields=['view_all_branches', 'view_all_warehouses', 'can_view_prices'])
    invalidate_user(target.pk)
    messages.success(request, 'تم تحديث إعدادات النطاق')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_set_screen_exception(request, pk):
    """إضافة/تحديث استثناء صلاحية على مستوى المستخدم يتغلّب على الأدوار."""
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    screen = Screen.objects.filter(pk=request.POST.get('screen'), is_active=True).first()
    if not screen:
        messages.error(request, 'اختر شاشة صحيحة')
        return redirect('access_control:user_detail', pk=target.pk)
    grant = request.POST.get('grant_type')
    grant = grant if grant in ('allow', 'deny') else 'allow'
    flags = {l: bool(request.POST.get(l)) for l in LEVELS}
    if not any(flags.values()):
        messages.error(request, 'حدّد مستوى واحداً على الأقل')
        return redirect('access_control:user_detail', pk=target.pk)
    UserScreenPermission.objects.update_or_create(
        user=target,
        screen=screen,
        defaults={
            'grant_type': grant,
            'can_view': flags['view'],
            'can_add': flags['add'],
            'can_edit': flags['edit'],
            'can_delete': flags['delete'],
            'can_print': flags['print'],
            'can_export': flags['export'],
        },
    )
    invalidate_user(target.pk)
    label = 'حرمان' if grant == 'deny' else 'سماح'
    messages.success(request, f'تم حفظ استثناء ({label}) على {screen.name}')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def user_remove_screen_exception(request, pk, item_pk):
    target, resp = _target_or_redirect(request, pk)
    if resp:
        return resp
    UserScreenPermission.objects.filter(pk=item_pk, user=target).delete()
    invalidate_user(target.pk)
    messages.success(request, 'تم إزالة الاستثناء')
    return redirect('access_control:user_detail', pk=target.pk)


@login_required
def role_list(request):
    """قائمة المجموعات (الأدوار) القابلة للتعديل."""
    if not _require_superuser(request):
        return redirect('dashboard')
    roles = Role.objects.annotate(screens=Count('screen_permissions'), users=Count('user_assignments')).order_by('name')
    rows = [{'role': role, 'screens': role.screens, 'users': role.users} for role in roles]
    return render(request, 'access_control/role_list.html', {'rows': rows})


@login_required
def role_create(request):
    """إنشاء مجموعة جديدة ثم الانتقال لتعديل صلاحياتها."""
    if not _require_superuser(request):
        return redirect('dashboard')
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        code = (request.POST.get('code') or '').strip()
        if not code:
            code = slugify(name, allow_unicode=False) or 'role'
        if not name:
            messages.error(request, 'اسم المجموعة مطلوب')
            return redirect('access_control:role_create')
        if Role.objects.filter(code=code).exists():
            messages.error(request, f'الكود "{code}" مستخدم بالفعل')
            return redirect('access_control:role_create')
        role = Role.objects.create(name=name, code=code, description=(request.POST.get('description') or '').strip())
        messages.success(request, 'تم إنشاء المجموعة، حدّد صلاحياتها الآن')
        return redirect('access_control:role_edit', pk=role.pk)
    return render(
        request, 'access_control/role_form.html', {'creating': True, 'levels': LEVELS, 'level_labels': LEVEL_LABELS}
    )


@login_required
def role_edit(request, pk):
    """تعديل بيانات المجموعة ومصفوفة صلاحياتها على الشاشات."""
    if not _require_superuser(request):
        return redirect('dashboard')
    role = get_object_or_404(Role, pk=pk)

    if request.method == 'POST':
        with transaction.atomic():
            if not role.is_system:
                name = (request.POST.get('name') or '').strip()
                if name:
                    role.name = name
                role.description = (request.POST.get('description') or '').strip()
            role.is_active = bool(request.POST.get('is_active'))
            role.save()

            existing = {p.screen_id: p for p in role.screen_permissions.all()}
            for screen in Screen.objects.filter(is_active=True):
                flags = {l: bool(request.POST.get(f'perm_{screen.id}_{l}')) for l in LEVELS}
                grant = request.POST.get(f'grant_{screen.id}') or 'allow'
                perm = existing.get(screen.id)
                if not any(flags.values()):
                    if perm:
                        perm.delete()
                    continue
                if not perm:
                    perm = RoleScreenPermission(role=role, screen=screen)
                perm.grant_type = grant if grant in ('allow', 'deny') else 'allow'
                perm.can_view = flags['view']
                perm.can_add = flags['add']
                perm.can_edit = flags['edit']
                perm.can_delete = flags['delete']
                perm.can_print = flags['print']
                perm.can_export = flags['export']
                perm.save()
        bump_global_version()
        messages.success(request, 'تم حفظ صلاحيات المجموعة')
        return redirect('access_control:role_edit', pk=role.pk)

    existing = {p.screen_id: p for p in role.screen_permissions.all()}
    modules = {}
    for screen in Screen.objects.filter(is_active=True):
        perm = existing.get(screen.id)
        cells = [{'level': l, 'checked': bool(perm and getattr(perm, f'can_{l}'))} for l in LEVELS]
        modules.setdefault(screen.module or 'أخرى', []).append(
            {'screen': screen, 'cells': cells, 'grant': perm.grant_type if perm else 'allow'}
        )
    module_rows = [{'module': m, 'screens': rows} for m, rows in modules.items()]

    return render(
        request,
        'access_control/role_form.html',
        {
            'creating': False,
            'role': role,
            'module_rows': module_rows,
            'levels': LEVELS,
            'level_labels': LEVEL_LABELS,
            'level_headers': [(l, LEVEL_LABELS[l]) for l in LEVELS],
        },
    )


@login_required
def role_delete(request, pk):
    """حذف مجموعة غير نظامية."""
    if not _require_superuser(request):
        return redirect('dashboard')
    role = get_object_or_404(Role, pk=pk)
    if request.method != 'POST':
        return redirect('access_control:role_edit', pk=role.pk)
    if role.is_system:
        messages.error(request, 'لا يمكن حذف مجموعة نظامية')
        return redirect('access_control:role_edit', pk=role.pk)
    role.delete()
    bump_global_version()
    messages.success(request, 'تم حذف المجموعة')
    return redirect('access_control:role_list')
