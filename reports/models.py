import uuid

from django.db import models


class ReportTemplate(models.Model):
    REPORT_TYPE_CHOICES = [
        ('income_statement', 'قائمة الدخل'),
        ('balance_sheet', 'الميزانية العمومية'),
        ('trial_balance', 'ميزان المراجعة'),
        ('vat_return', 'إقرار ضريبة القيمة المضافة'),
        ('withholding_tax', 'ضريبة الخصم والتحصيل'),
        ('supplier_report', 'تقرير الموردين'),
        ('customer_report', 'تقرير العملاء'),
        ('profit_margin', 'تقرير نسب الربح'),
        ('asset_schedule', 'جدول الأصول والإهلاك'),
        ('payroll_report', 'تقرير الرواتب'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم التقرير')
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES, verbose_name='نوع التقرير')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'قالب تقرير'
        verbose_name_plural = 'قوالب التقارير'
        ordering = ['name']

    def __str__(self):
        return self.name
