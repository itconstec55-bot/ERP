import uuid

from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from common.models import SequenceNumber
from common.decimal_utils import quantize_10, safe_mul, safe_add


class RFQ(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('sent', 'مُرسل'),
        ('closed', 'مغلق'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=50, unique=True, blank=True,
                              verbose_name='رقم الطلب')
    requisition = models.ForeignKey(
        'requisitions.Requisition', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rfqs', verbose_name='الطلب الداخلي')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='rfqs_requested', verbose_name='طالب الشراء')
    cost_center = models.ForeignKey(
        'budget.CostCenter', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='مركز التكلفة')
    date = models.DateField(default=timezone.localdate, verbose_name='التاريخ')
    valid_until = models.DateField(null=True, blank=True, verbose_name='صالح حتى')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft',
                              verbose_name='الحالة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='rfqs_created', verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'طلب عروض أسعار'
        verbose_name_plural = 'طلبات عروض الأسعار'
        ordering = ['-date', '-number']
        permissions = [
            ('approve_rfq', 'اعتماد طلب عروض أسعار'),
            ('send_rfq', 'إرسال طلب عروض أسعار'),
            ('close_rfq', 'إغلاق طلب عروض أسعار'),
            ('convert_rfq', 'تحويل طلب عروض أسعار إلى أمر شراء'),
        ]

    def __str__(self):
        return f'{self.number or "—"} - {self.requested_by or ""}'

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = SequenceNumber.get_next_number('rfq')
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('rfq:rfq_detail', args=[self.pk])

    def total_estimated(self):
        return safe_add(*[line.line_total for line in self.lines.all()])


class RFQLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='lines',
                           verbose_name='طلب عروض الأسعار')
    product = models.ForeignKey('purchases.Product', on_delete=models.PROTECT,
                               verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=15, decimal_places=3, verbose_name='الكمية')
    required_date = models.DateField(null=True, blank=True, verbose_name='تاريخ التوريد المطلوب')
    estimated_unit_price = models.DecimalField(max_digits=15, decimal_places=2,
                                              null=True, blank=True, verbose_name='السعر التقديري')
    description = models.CharField(max_length=255, blank=True, verbose_name='وصف إضافي')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'بند طلب عرض السعر'
        verbose_name_plural = 'بنود طلب عروض الأسعار'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    @property
    def line_total(self):
        return safe_mul(self.quantity, self.estimated_unit_price or 0)


class Quotation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'معلق'),
        ('accepted', 'مقبول'),
        ('rejected', 'مرفوض'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='quotations',
                           verbose_name='طلب عروض الأسعار')
    supplier = models.ForeignKey('purchases.Supplier', on_delete=models.PROTECT,
                                verbose_name='المورد')
    received_date = models.DateField(default=timezone.localdate, verbose_name='تاريخ الاستلام')
    valid_until = models.DateField(null=True, blank=True, verbose_name='صالح حتى')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending',
                             verbose_name='الحالة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='quotations_created', verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'عرض سعر مورد'
        verbose_name_plural = 'عروض أسعار الموردين'
        ordering = ['-received_date', '-created_at']
        permissions = [
            ('accept_quotation', 'قبول عرض السعر'),
            ('reject_quotation', 'رفض عرض السعر'),
        ]

    def __str__(self):
        return f'{self.supplier.name} - {self.rfq.number or ""}'

    @property
    def total(self):
        return safe_add(*[line.line_total for line in self.lines.all()])


class QuotationLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='lines',
                                 verbose_name='عرض السعر')
    rfq_line = models.ForeignKey(RFQLine, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='quotation_lines', verbose_name='بند الطلب')
    product = models.ForeignKey('purchases.Product', on_delete=models.PROTECT,
                               verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=15, decimal_places=3, verbose_name='الكمية')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='سعر الوحدة')
    discount = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                  verbose_name='الخصم')
    delivery_days = models.IntegerField(null=True, blank=True, verbose_name='أيام التسليم')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'بند عرض السعر'
        verbose_name_plural = 'بنود عروض الأسعار'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    @property
    def line_total(self):
        return safe_mul(self.quantity, self.unit_price) - (self.discount or 0)
