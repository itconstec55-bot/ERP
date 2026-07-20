from datetime import date
from django.db import models, transaction


class SequenceNumber(models.Model):
    SEQUENCE_TYPES = [
        ('sales_invoice', 'فواتير المبيعات'),
        ('purchase_invoice', 'فواتير المشتريات'),
        ('receipt', 'سندات القبض'),
        ('payment', 'سندات الدفع'),
        ('sales_return', 'مرتجعات المبيعات'),
        ('purchase_return', 'مرتجعات المشتريات'),
        ('journal_entry', 'القيود المحاسبية'),
        ('purchase_order', 'أوامر الشراء'),
        ('sales_order', 'أوامر البيع'),
        ('goods_received', 'إيصالات استلام البضاعة'),
        ('requisition', 'طلبات الشراء'),
    ]

    sequence_type = models.CharField(max_length=30, choices=SEQUENCE_TYPES, verbose_name='النوع')
    prefix = models.CharField(max_length=10, default='', verbose_name='البادئة')
    year = models.IntegerField(default=date.today().year, verbose_name='السنة')
    last_number = models.IntegerField(default=0, verbose_name='آخر رقم')

    class Meta:
        verbose_name = 'رقم تسلسلي'
        verbose_name_plural = 'الأرقام التسلسلية'
        unique_together = ['sequence_type', 'year']

    def __str__(self):
        return f'{self.sequence_type} - {self.year}: {self.last_number}'

    @classmethod
    def get_next_number(cls, sequence_type, year=None):
        if year is None:
            year = date.today().year
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(
                sequence_type=sequence_type, year=year,
                defaults={'last_number': 0, 'prefix': cls._default_prefix(sequence_type)},
            )
            seq.last_number += 1
            seq.save(update_fields=['last_number'])
            return f'{seq.prefix}{year}-{seq.last_number:04d}'

    @staticmethod
    def _default_prefix(sequence_type):
        return {
            'sales_invoice': 'SI-', 'purchase_invoice': 'PI-',
            'receipt': 'RCP-', 'payment': 'PMT-',
            'sales_return': 'SR-', 'purchase_return': 'PR-',
            'journal_entry': 'JE-',
            'purchase_order': 'PO-', 'sales_order': 'SO-', 'goods_received': 'GRN-',
            'requisition': 'REQ-',
            'CR': 'CR-', 'PO': 'PO-', 'CTR': 'CTR-',
            'IC': 'IC-', 'CP': 'CP-', 'B': 'B-',
        }.get(sequence_type, '')

    @classmethod
    def initialize_defaults(cls):
        for seq_type, _ in cls.SEQUENCE_TYPES:
            cls.objects.get_or_create(
                sequence_type=seq_type,
                year=date.today().year,
                defaults={'last_number': 0},
            )


"""
نماذج الطابور الخاص بواتساب
"""
import uuid
from django.db import models
from django.utils import timezone


class WhatsAppMessageQueue(models.Model):
    """قاعدة بيانات لرسائل واتساب المرسلة/المجدولة"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    message = models.TextField(verbose_name='نص الرسالة')
    message_type = models.CharField(max_length=20, default="text", verbose_name='نوع الرسالة')
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'معلق'),
            ('queued', 'في الطابور'),
            ('sent', 'مرسل'),
            ('delivered', 'تم التسليم'),
            ('read', 'مقروء'),
            ('failed', 'فشل'),
            ('expired', 'منتهي الصلاحية'),
        ],
        default='pending',
        verbose_name='الحالة'
    )
    priority = models.IntegerField(default=0, verbose_name='الأولوية')
    max_retries = models.IntegerField(default=3, verbose_name='أقصى محاولات')
    retry_count = models.IntegerField(default=0, verbose_name='عدد المحاولات')
    error_message = models.TextField(blank=True, null=True, verbose_name='رسالة الخطأ')
    error_code = models.CharField(max_length=50, blank=True, null=True, verbose_name='كود الخطأ')
    meta_message_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='معرف رسالة ميتا')
    webhook_data = models.JSONField(default=dict, blank=True, verbose_name='بيانات الويب هوك')
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='مجدول في')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='أرسل في')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='سلم في')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'priority', 'scheduled_at']),
            models.Index(fields=['phone', 'status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-priority', 'scheduled_at', 'created_at']
        verbose_name = 'رسالة واتساب'
        verbose_name_plural = 'طابور رسائل واتساب'
    
    def __str__(self):
        return f"{self.phone} - {self.status}"


class UserProfile(models.Model):
    """ملحق المستخدم: الفرع الافتراضي وصلاحيات على مستوى الكائن."""
    ACCOUNT_TYPE_CHOICES = [
        ('admin', 'مدير النظام'),
        ('manager', 'مدير'),
        ('accountant', 'محاسب'),
        ('warehouse_keeper', 'أمين مخزن'),
        ('sales', 'مبيعات'),
        ('purchasing', 'مشتريات'),
        ('viewer', 'مشاهدة فقط'),
    ]

    user = models.OneToOneField(
        'auth.User', on_delete=models.CASCADE, related_name='userprofile',
        verbose_name='المستخدم')
    branch = models.ForeignKey(
        'company.CompanyBranch', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='الفرع', help_text='يحدّ مشاهدة السجلات المرتبطة بفرع المستخدم فقط')
    account_type = models.CharField(
        max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='viewer',
        verbose_name='نوع الحساب الوظيفي')
    view_all_branches = models.BooleanField(
        default=False, verbose_name='صلاحية مشاهدة كل الفروع')
    view_all_warehouses = models.BooleanField(
        default=False, verbose_name='صلاحية مشاهدة كل المخازن')
    can_view_prices = models.BooleanField(
        default=True, verbose_name='صلاحية مشاهدة الأسعار والتكلفة')
    valid_from = models.DateField(
        null=True, blank=True, verbose_name='صالح من')
    valid_until = models.DateField(
        null=True, blank=True, verbose_name='صالح حتى')

    class Meta:
        verbose_name = 'ملف المستخدم'
        verbose_name_plural = 'ملفات المستخدمين'

    def __str__(self):
        return f'{self.user.username} - {self.branch or "بدون فرع"}'

    def is_within_validity(self):
        from datetime import date
        today = date.today()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False
        return True