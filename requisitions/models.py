import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from budget.models import CostCenter
from common.decimal_utils import quantize_10, safe_mul
from common.models import SequenceNumber
from purchases.models import Product, UnitOfMeasure


class Requisition(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('pending', 'بانتظار الموافقة'),
        ('approved', 'معتمد'),
        ('rejected', 'مرفوض'),
        ('ordered', 'تم الطلب'),
        ('cancelled', 'ملغي'),
    ]

    PRIORITY_CHOICES = [('low', 'منخفض'), ('medium', 'متوسط'), ('high', 'عالي')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, blank=True, verbose_name='رقم طلب الشراء')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requisitions_requested',
        verbose_name='طالب الشراء',
    )
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='مركز التكلفة'
    )
    date = models.DateField(verbose_name='التاريخ')
    need_by_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الحاجة')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', verbose_name='الأولوية')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requisitions_created',
        verbose_name='أنشئ بواسطة',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'طلب شراء'
        verbose_name_plural = 'طلبات الشراء'
        ordering = ['-date', '-number']
        permissions = [
            ('approve_requisition', 'اعتماد طلب شراء'),
            ('reject_requisition', 'رفض طلب شراء'),
            ('submit_requisition', 'تقديم طلب شراء للموافقة'),
            ('convert_requisition', 'تحويل طلب الشراء لمرحلة لاحقة'),
            ('cancel_requisition', 'إلغاء طلب شراء'),
        ]

    def __str__(self):
        return f'{self.number} - {self.requested_by}'

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = SequenceNumber.get_next_number('requisition')
        if not self.date:
            from datetime import date

            self.date = date.today()
        super().save(*args, **kwargs)

    @property
    def total(self):
        return sum(quantize_10(line.line_total) for line in self.lines.all())

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse('requisitions:req_detail', args=[self.pk])


class RequisitionLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requisition = models.ForeignKey(
        Requisition, on_delete=models.CASCADE, related_name='lines', verbose_name='طلب الشراء'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=15, decimal_places=3, verbose_name='الكمية')
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='وحدة القياس')
    estimated_unit_price = models.DecimalField(
        max_digits=20, decimal_places=10, null=True, blank=True, verbose_name='السعر التقديري للوحدة'
    )
    required_date = models.DateField(null=True, blank=True, verbose_name='تاريخ التوريد المطلوب')
    notes = models.CharField(max_length=255, blank=True, verbose_name='ملاحظات')

    class Meta:
        verbose_name = 'بند طلب شراء'
        verbose_name_plural = 'بنود طلب الشراء'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    @property
    def line_total(self):
        if self.estimated_unit_price is None:
            return Decimal('0')
        return safe_mul(self.quantity, self.estimated_unit_price)
