import uuid

from django.contrib.auth.models import User
from django.db import models, transaction
from django.utils import timezone

from accounts.models import Account, JournalEntry


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم القسم')
    manager = models.CharField(max_length=200, blank=True, null=True, verbose_name='مدير القسم')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'قسم'
        verbose_name_plural = 'الأقسام'
        ordering = ['name']

    def __str__(self):
        return self.name


class Employee(models.Model):
    GENDER_CHOICES = [('male', 'ذكر'), ('female', 'أنثى')]
    MARITAL_STATUS_CHOICES = [('single', 'أعزب'), ('married', 'متزوج'), ('divorced', 'مطلق'), ('widowed', 'أرمل')]
    STATUS_CHOICES = [('active', 'نشط'), ('inactive', 'غير نشط'), ('terminated', 'تم الفصل')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee_number = models.CharField(max_length=20, unique=True, verbose_name='رقم الموظف')
    first_name = models.CharField(max_length=100, verbose_name='الاسم الأول')
    last_name = models.CharField(max_length=100, verbose_name='الاسم الأخير')
    national_id = models.CharField(max_length=20, unique=True, verbose_name='رقم الهوية')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name='الجنس')
    date_of_birth = models.DateField(blank=True, null=True, verbose_name='تاريخ الميلاد')
    marital_status = models.CharField(
        max_length=20, choices=MARITAL_STATUS_CHOICES, default='single', verbose_name='الحالة الاجتماعية'
    )
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القسم')
    position = models.CharField(max_length=200, verbose_name='الوظيفة')
    hire_date = models.DateField(verbose_name='تاريخ التعيين')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='التليفون')
    mobile = models.CharField(max_length=20, blank=True, null=True, verbose_name='المحمول')
    email = models.EmailField(blank=True, null=True, verbose_name='البريد الإلكتروني')
    address = models.TextField(blank=True, null=True, verbose_name='العنوان')
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='الراتب الأساسي')
    social_insurance_number = models.CharField(
        max_length=50, blank=True, null=True, verbose_name='رقم التأمين الاجتماعي'
    )
    tax_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='الرقم الضريبي')
    bank_account = models.CharField(max_length=50, blank=True, null=True, verbose_name='رقم الحساب البنكي')
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الحساب المحاسبي'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active', db_index=True, verbose_name='الحالة'
    )
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'موظف'
        verbose_name_plural = 'الموظفين'
        ordering = ['employee_number']
        permissions = [
            ('approve_salary', 'اعتماد راتب'),
            ('print_salary', 'طباعة كشف راتب'),
            ('export_salary', 'تصدير الرواتب'),
        ]

    def __str__(self):
        return f'{self.employee_number} - {self.first_name} {self.last_name}'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'


class Attendance(models.Model):
    STATUS_CHOICES = [('present', 'حاضر'), ('absent', 'غائب'), ('late', 'متأخر'), ('leave', 'إجازة'), ('sick', 'مرضي')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='الموظف', related_name='attendances')
    date = models.DateField(verbose_name='التاريخ')
    check_in = models.TimeField(blank=True, null=True, verbose_name='وقت الحضور')
    check_out = models.TimeField(blank=True, null=True, verbose_name='وقت الانصراف')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present', verbose_name='الحالة')
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='ساعات العمل الإضافي')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سجل حضور'
        verbose_name_plural = 'سجلات الحضور'
        unique_together = ['employee', 'date']
        ordering = ['-date']

    def __str__(self):
        return f'{self.employee.full_name} - {self.date}'


class Salary(models.Model):
    MONTH_CHOICES = [
        (1, 'يناير'),
        (2, 'فبراير'),
        (3, 'مارس'),
        (4, 'أبريل'),
        (5, 'مايو'),
        (6, 'يونيو'),
        (7, 'يوليو'),
        (8, 'أغسطس'),
        (9, 'سبتمبر'),
        (10, 'أكتوبر'),
        (11, 'نوفمبر'),
        (12, 'ديسمبر'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='الموظف', related_name='salaries')
    month = models.IntegerField(choices=MONTH_CHOICES, verbose_name='الشهر')
    year = models.IntegerField(verbose_name='السنة')
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='الراتب الأساسي')
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='البدلات')
    overtime = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='العمل الإضافي')
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='المكافآت')
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='الخصومات')
    social_insurance = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='التأمين الاجتماعي')
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='ضريبة الدخل')
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='صافي الراتب')
    is_paid = models.BooleanField(default=False, verbose_name='تم الدفع')
    payment_date = models.DateField(blank=True, null=True, verbose_name='تاريخ الدفع')
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القيد المحاسبي'
    )
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'راتب'
        verbose_name_plural = 'الرواتب'
        unique_together = ['employee', 'month', 'year']
        ordering = ['-year', '-month']

    def __str__(self):
        return f'{self.employee.full_name} - {self.month}/{self.year}'

    def calculate_net_salary(self):
        gross = self.basic_salary + self.allowances + self.overtime + self.bonus
        total_deductions = self.deductions + self.social_insurance + self.income_tax
        self.net_salary = gross - total_deductions
        if self.pk:
            self.save(update_fields=['net_salary'])

    def create_journal_entry(self):
        from common.accounting_service import JournalEntryService

        if self.journal_entry:
            raise ValueError('تم ترحيل الراتب بالفعل')

        self.calculate_net_salary()
        total_gross = self.basic_salary + self.allowances + self.overtime + self.bonus
        lines = [
            {
                'account': JournalEntryService.get_account('5300'),
                'debit': total_gross,
                'credit': 0,
                'description': f'رواتب - {self.employee.full_name}',
            },
            {
                'account': JournalEntryService.get_account('2300'),
                'debit': 0,
                'credit': self.net_salary,
                'description': f'صافي راتب - {self.employee.full_name}',
            },
        ]
        if self.social_insurance > 0:
            lines.append(
                {
                    'account': JournalEntryService.get_account('2310'),
                    'debit': 0,
                    'credit': self.social_insurance,
                    'description': 'التأمين الاجتماعي',
                }
            )
        if self.income_tax > 0:
            lines.append(
                {
                    'account': JournalEntryService.get_account('2320'),
                    'debit': 0,
                    'credit': self.income_tax,
                    'description': 'ضريبة الدخل المستحقة',
                }
            )
        if self.deductions > 0:
            lines.append(
                {
                    'account': JournalEntryService.get_account('2330'),
                    'debit': 0,
                    'credit': self.deductions,
                    'description': 'الخصومات الأخرى',
                }
            )
        from datetime import date

        with transaction.atomic():
            entry = JournalEntryService.create_entry(
                entry_type='payroll',
                date=self.payment_date or date.today(),
                description=f'رواتب {self.employee.full_name} - {self.month}/{self.year}',
                reference=f'SAL-{self.employee.employee_number}-{self.year}-{self.month}',
                lines=lines,
                created_by=self.created_by,
            )
            self.journal_entry = entry
            self.save(update_fields=['journal_entry'])


class Contract(models.Model):
    CONTRACT_TYPE_CHOICES = [
        ('permanent', 'دائم'),
        ('temporary', 'مؤقت'),
        ('part_time', 'دوام جزئي'),
        ('internship', 'تدريب'),
        ('freelance', 'عمل حر'),
    ]
    STATUS_CHOICES = [('active', 'نشط'), ('expired', 'منتهي'), ('terminated', 'ملغي')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='contracts', verbose_name='الموظف')
    contract_number = models.CharField(max_length=50, unique=True, verbose_name='رقم العقد')
    contract_type = models.CharField(
        max_length=20, choices=CONTRACT_TYPE_CHOICES, default='permanent', verbose_name='نوع العقد'
    )
    start_date = models.DateField(verbose_name='تاريخ البداية')
    end_date = models.DateField(blank=True, null=True, verbose_name='تاريخ النهاية')
    salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='الراتب')
    probation_period_months = models.IntegerField(default=3, verbose_name='فترة التجربة (أشهر)')
    annual_leave_days = models.IntegerField(default=21, verbose_name='أيام الإجازة السنوية')
    notice_period_days = models.IntegerField(default=30, verbose_name='أيام فترة الإشعار')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active', db_index=True, verbose_name='الحالة'
    )
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='hr_contracts_created', verbose_name='أنشئ بواسطة'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'عقد عمل'
        verbose_name_plural = 'عقود العمل'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.contract_number} - {self.employee.full_name}'

    @property
    def is_active(self):
        if self.status == 'terminated':
            return False
        if self.end_date and self.end_date < timezone.now().date():
            return False
        return self.status == 'active'

    def save(self, *args, **kwargs):
        if self.end_date and self.end_date < timezone.now().date() and self.status == 'active':
            self.status = 'expired'
        super().save(*args, **kwargs)


class LeaveType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='نوع الإجازة')
    days_per_year = models.IntegerField(default=0, verbose_name='الأيام سنوياً')
    is_paid = models.BooleanField(default=True, verbose_name='مدفوعة')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'نوع إجازة'
        verbose_name_plural = 'أنواع الإجازات'

    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'قيد المراجعة'),
        ('approved', 'معتمدة'),
        ('rejected', 'مرفوضة'),
        ('cancelled', 'ملغاة'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leaves', verbose_name='الموظف')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, verbose_name='نوع الإجازة')
    start_date = models.DateField(verbose_name='من تاريخ')
    end_date = models.DateField(verbose_name='إلى تاريخ')
    days = models.IntegerField(verbose_name='عدد الأيام')
    reason = models.TextField(blank=True, null=True, verbose_name='السبب')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True, verbose_name='الحالة'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leaves_approved',
        verbose_name='اعتمد بواسطة',
    )
    approved_date = models.DateTimeField(blank=True, null=True, verbose_name='تاريخ الاعتماد')
    rejection_reason = models.TextField(blank=True, null=True, verbose_name='سبب الرفض')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='leaves_created', verbose_name='أنشئ بواسطة'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'طلب إجازة'
        verbose_name_plural = 'طلبات الإجازات'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee.full_name} - {self.leave_type.name} ({self.start_date} to {self.end_date})'

    @property
    def remaining_days(self):
        used = (
            LeaveRequest.objects.filter(
                employee=self.employee,
                leave_type=self.leave_type,
                status='approved',
                start_date__year=timezone.now().year,
            ).aggregate(total=models.Sum('days'))['total']
            or 0
        )
        return self.leave_type.days_per_year - used

    def approve(self, user):
        self.status = 'approved'
        self.approved_by = user
        self.approved_date = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_date'])

    def reject(self, user, reason=''):
        self.status = 'rejected'
        self.approved_by = user
        self.approved_date = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=['status', 'approved_by', 'approved_date', 'rejection_reason'])
