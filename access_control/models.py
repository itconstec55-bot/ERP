import uuid
from django.db import models
from django.contrib.auth.models import User


GRANT_TYPES = [
    ('allow', 'سماح'),
    ('deny', 'حرمان صريح'),
]


class Role(models.Model):
    """دور مستقل: حاوية صلاحيات قابلة لإعادة الاستخدام يُسنَد لعدة مستخدمين."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='اسم الدور')
    code = models.CharField(max_length=50, unique=True, verbose_name='كود الدور')
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_system = models.BooleanField(
        default=False, verbose_name='دور نظامي',
        help_text='الأدوار النظامية جاهزة ولا يمكن حذفها')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'دور'
        verbose_name_plural = 'الأدوار'
        ordering = ['name']

    def __str__(self):
        return self.name


class Screen(models.Model):
    """تعريف شاشات النظام كبيانات (لا ثوابت مشفّرة) لدعم التوسّع."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=100, unique=True, verbose_name='كود الشاشة',
        help_text='مثل: sales.invoice')
    name = models.CharField(max_length=150, verbose_name='اسم الشاشة')
    module = models.CharField(max_length=100, blank=True, verbose_name='الوحدة')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    class Meta:
        verbose_name = 'شاشة'
        verbose_name_plural = 'الشاشات'
        ordering = ['module', 'order', 'name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class ScreenAccessMixin(models.Model):
    """المستويات الست الموحّدة للوصول على الشاشة."""
    can_view = models.BooleanField(default=False, verbose_name='مشاهدة')
    can_add = models.BooleanField(default=False, verbose_name='إضافة')
    can_edit = models.BooleanField(default=False, verbose_name='تعديل')
    can_delete = models.BooleanField(default=False, verbose_name='حذف')
    can_print = models.BooleanField(default=False, verbose_name='طباعة')
    can_export = models.BooleanField(default=False, verbose_name='تصدير')

    LEVELS = ('view', 'add', 'edit', 'delete', 'print', 'export')

    class Meta:
        abstract = True

    def levels_dict(self):
        return {
            'view': self.can_view, 'add': self.can_add, 'edit': self.can_edit,
            'delete': self.can_delete, 'print': self.can_print, 'export': self.can_export,
        }


class RoleScreenPermission(ScreenAccessMixin):
    """صلاحيات دور على شاشة."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name='screen_permissions',
        verbose_name='الدور')
    screen = models.ForeignKey(
        Screen, on_delete=models.CASCADE, related_name='role_permissions',
        verbose_name='الشاشة')
    grant_type = models.CharField(
        max_length=10, choices=GRANT_TYPES, default='allow', verbose_name='نوع المنح')

    class Meta:
        verbose_name = 'صلاحية دور على شاشة'
        verbose_name_plural = 'صلاحيات الأدوار على الشاشات'
        unique_together = ['role', 'screen']

    def __str__(self):
        return f'{self.role} → {self.screen}'


class UserScreenPermission(ScreenAccessMixin):
    """استثناء صلاحيات على مستوى المستخدم يتغلّب على ما ورثه من الأدوار."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='screen_permissions',
        verbose_name='المستخدم')
    screen = models.ForeignKey(
        Screen, on_delete=models.CASCADE, related_name='user_permissions',
        verbose_name='الشاشة')
    grant_type = models.CharField(
        max_length=10, choices=GRANT_TYPES, default='allow', verbose_name='نوع المنح')

    class Meta:
        verbose_name = 'استثناء صلاحية مستخدم'
        verbose_name_plural = 'استثناءات صلاحيات المستخدمين'
        unique_together = ['user', 'screen']

    def __str__(self):
        return f'{self.user} → {self.screen} ({self.get_grant_type_display()})'


class UserRoleAssignment(models.Model):
    """إسناد دور لمستخدم (يدعم أدواراً متعددة)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='role_assignments',
        verbose_name='المستخدم')
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name='user_assignments',
        verbose_name='الدور')
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='granted_roles', verbose_name='مُنِح بواسطة')
    granted_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateField(null=True, blank=True, verbose_name='صالح حتى')

    class Meta:
        verbose_name = 'إسناد دور'
        verbose_name_plural = 'إسنادات الأدوار'
        unique_together = ['user', 'role']

    def __str__(self):
        return f'{self.user} = {self.role}'


class UserBranch(models.Model):
    """نطاق الفروع المخوّلة للمستخدم."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='allowed_branches',
        verbose_name='المستخدم')
    branch = models.ForeignKey(
        'company.CompanyBranch', on_delete=models.CASCADE,
        related_name='authorized_users', verbose_name='الفرع')
    is_default = models.BooleanField(default=False, verbose_name='الفرع الافتراضي')
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فرع مخوّل'
        verbose_name_plural = 'الفروع المخوّلة'
        unique_together = ['user', 'branch']

    def __str__(self):
        return f'{self.user} @ {self.branch}'


class UserWarehouse(models.Model):
    """نطاق المخازن المخوّلة للمستخدم مع أعلام العمليات."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='allowed_warehouses',
        verbose_name='المستخدم')
    warehouse = models.ForeignKey(
        'warehouses.Warehouse', on_delete=models.CASCADE,
        related_name='authorized_users', verbose_name='المخزن')
    can_receive = models.BooleanField(default=False, verbose_name='استلام')
    can_issue = models.BooleanField(default=False, verbose_name='صرف')
    can_count = models.BooleanField(default=False, verbose_name='جرد')
    can_transfer = models.BooleanField(default=False, verbose_name='تحويل')

    class Meta:
        verbose_name = 'مخزن مخوّل'
        verbose_name_plural = 'المخازن المخوّلة'
        unique_together = ['user', 'warehouse']

    def __str__(self):
        return f'{self.user} @ {self.warehouse}'


class UserAccountTypeScope(models.Model):
    """تقييد المستخدم على فئات الحسابات المحاسبية."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='allowed_account_types',
        verbose_name='المستخدم')
    account_type = models.ForeignKey(
        'accounts.AccountType', on_delete=models.CASCADE,
        related_name='authorized_users', verbose_name='نوع الحساب')
    can_view = models.BooleanField(default=True, verbose_name='مشاهدة')
    can_transact = models.BooleanField(default=False, verbose_name='إجراء حركات')

    class Meta:
        verbose_name = 'نطاق نوع حساب'
        verbose_name_plural = 'نطاقات أنواع الحسابات'
        unique_together = ['user', 'account_type']

    def __str__(self):
        return f'{self.user} → {self.account_type}'
