import uuid
from django.db import models, transaction
from django.contrib.auth.models import User
from accounts.models import Account
from hr.models import Department


class DocumentType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود النوع')
    name = models.CharField(max_length=200, verbose_name='اسم نوع المستند')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    prefix = models.CharField(max_length=10, verbose_name='بادئة الرقم')
    next_number = models.IntegerField(default=1, verbose_name='التالي رقم')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'نوع مستند'
        verbose_name_plural = 'أنواع المستندات'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def generate_number(self):
        with transaction.atomic():
            locked = DocumentType.objects.select_for_update().get(pk=self.pk)
            num = locked.next_number
            locked.next_number += 1
            locked.save(update_fields=['next_number'])
            return f'{locked.prefix}-{num:04d}'


class DocumentTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم القالب')
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE,
                                       related_name='templates', verbose_name='نوع المستند')
    content = models.TextField(verbose_name='محتوى القالب')
    is_default = models.BooleanField(default=False, verbose_name='القالب الافتراضي')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قالب مستند'
        verbose_name_plural = 'قوالب المستندات'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.document_type})'


class Document(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('pending', 'قيد المراجعة'),
        ('approved', 'معتمد'),
        ('rejected', 'مرفوض'),
        ('archived', 'مؤرشف'),
        ('cancelled', 'ملغي'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'منخفضة'),
        ('medium', 'متوسطة'),
        ('high', 'عالية'),
        ('urgent', 'عاجلة'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_number = models.CharField(max_length=50, unique=True, verbose_name='رقم المستند')
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT,
                                       related_name='documents', verbose_name='نوع المستند')
    title = models.CharField(max_length=300, verbose_name='عنوان المستند')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    date = models.DateField(verbose_name='التاريخ')
    due_date = models.DateField(blank=True, null=True, verbose_name='تاريخ الاستحقاق')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft',
                               db_index=True, verbose_name='الحالة')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium',
                                 verbose_name='الأولوية')

    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='documents', verbose_name='القسم')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='created_documents', verbose_name='أنشئ بواسطة')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='assigned_documents', verbose_name='مسؤول التنفيذ')

    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='الحساب المحاسبي المرتبط')
    reference_amount = models.DecimalField(max_digits=15, decimal_places=10, default=0,
                                            verbose_name='المبلغ المرجعي')
    reference_number = models.CharField(max_length=100, blank=True, null=True,
                                         verbose_name='رقم المرجع الخارجي')

    is_active = models.BooleanField(default=True, verbose_name='نشط')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مستند'
        verbose_name_plural = 'المستندات'
        ordering = ['-date', '-document_number']

    def __str__(self):
        return f'{self.document_number} - {self.title}'

    VALID_TRANSITIONS = {
        'draft': ['pending', 'cancelled'],
        'pending': ['approved', 'rejected'],
        'approved': ['archived'],
        'rejected': ['draft', 'cancelled'],
        'archived': [],
        'cancelled': [],
    }

    def _validate_transition(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f'لا يمكن التحويل من حالة "{self.get_status_display()}" إلى "{dict(self.STATUS_CHOICES).get(new_status, new_status)}"'
            )

    def approve(self):
        self._validate_transition('approved')
        self.status = 'approved'
        self.save(update_fields=['status', 'updated_at'])

    def reject(self):
        self._validate_transition('rejected')
        self.status = 'rejected'
        self.save(update_fields=['status', 'updated_at'])

    def archive(self):
        self._validate_transition('archived')
        self.status = 'archived'
        self.save(update_fields=['status', 'updated_at'])

    def cancel(self):
        self._validate_transition('cancelled')
        self.status = 'cancelled'
        self.save(update_fields=['status', 'updated_at'])


class DocumentFlow(models.Model):
    ACTION_CHOICES = [
        ('create', 'إنشاء'),
        ('submit', 'تقديم'),
        ('review', 'مراجعة'),
        ('approve', 'اعتماد'),
        ('reject', 'رفض'),
        ('archive', 'أرشفة'),
        ('cancel', 'إلغاء'),
        ('comment', 'تعليق'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE,
                                  related_name='flows', verbose_name='المستند')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='الإجراء')
    from_status = models.CharField(max_length=20, blank=True, null=True, verbose_name='من حالة')
    to_status = models.CharField(max_length=20, blank=True, null=True, verbose_name='إلى حالة')
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                      verbose_name='نفّذ الإجراء')
    comment = models.TextField(blank=True, null=True, verbose_name='التعليق')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تدفق مستند'
        verbose_name_plural = 'حركات المستندات'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.document.document_number} - {self.get_action_display()}'


class DocumentAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE,
                                  related_name='attachments', verbose_name='المستند')
    file = models.FileField(upload_to='documents/attachments/%Y/%m/', verbose_name='الملف')
    name = models.CharField(max_length=200, verbose_name='اسم الملف')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     verbose_name='رفع بواسطة')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مرفق مستند'
        verbose_name_plural = 'مرفقات المستندات'
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name
