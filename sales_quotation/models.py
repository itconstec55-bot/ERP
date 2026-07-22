import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models

from common.decimal_utils import quantize_10, safe_mul
from common.models import SequenceNumber
from purchases.models import Product
from sales.models import Customer


class SalesQuotation(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('sent', 'مرسلة'),
        ('accepted', 'مقبولة'),
        ('rejected', 'مرفوضة'),
        ('expired', 'منتهية الصلاحية'),
        ('converted', 'محولة لفاتورة'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation_number = models.CharField(max_length=50, unique=True, verbose_name='رقم العرض')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name='العميل')
    date = models.DateField(verbose_name='التاريخ')
    valid_until = models.DateField(verbose_name='صالح حتى')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True, verbose_name='الحالة'
    )
    payment_terms = models.CharField(max_length=200, blank=True, verbose_name='شروط الدفع')
    delivery_terms = models.CharField(max_length=200, blank=True, verbose_name='شروط التسليم')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    subtotal = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='الإجمالي قبل الضريبة')
    vat_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='الضريبة')
    total_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='الإجمالي')
    converted_invoice = models.ForeignKey(
        'sales.SalesInvoice', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الفاتورة المحولة'
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'عرض سعر مبيعات'
        verbose_name_plural = 'عروض أسعار المبيعات'
        ordering = ['-date', '-quotation_number']

    def __str__(self):
        return f'{self.quotation_number} - {self.customer.name}'

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            self.quotation_number = SequenceNumber.get_next_number('sales_quotation')
        super().save(*args, **kwargs)

    def calculate_totals(self):
        from decimal import Decimal

        self.subtotal = sum(quantize_10(line.line_total) for line in self.lines.all())
        if self.subtotal > 0:
            self.vat_amount = quantize_10(self.subtotal * Decimal('0.14'))
        else:
            self.vat_amount = Decimal('0')
        self.total_amount = self.subtotal + self.vat_amount
        self.save(update_fields=['subtotal', 'vat_amount', 'total_amount'])


class SalesQuotationLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(SalesQuotation, on_delete=models.CASCADE, related_name='lines', verbose_name='العرض')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='المنتج')
    description = models.CharField(max_length=300, blank=True, verbose_name='الوصف')
    quantity = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='الكمية')
    unit_price = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='سعر الوحدة')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الخصم')
    total_price = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='الإجمالي')

    class Meta:
        verbose_name = 'بند عرض سعر'
        verbose_name_plural = 'بنود عروض الأسعار'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    @property
    def line_total(self):
        total = safe_mul(self.quantity, self.unit_price)
        if self.discount_percent > 0:
            total = total - safe_mul(total, self.discount_percent / Decimal('100'))
        return total

    def save(self, *args, **kwargs):
        self.total_price = self.line_total
        super().save(*args, **kwargs)
