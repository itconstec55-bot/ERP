from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
import uuid

from sales.models import Customer
from purchases.models import Product
from common.models import SequenceNumber
from common.decimal_utils import quantize_10, safe_mul


class SalesOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكد'),
        ('invoiced', 'مفوتر'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, blank=True,
                                    verbose_name='رقم أمر البيع')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name='العميل')
    date = models.DateField(verbose_name='التاريخ')
    expected_date = models.DateField(blank=True, null=True, verbose_name='تاريخ التسليم المتوقع')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft',
                              verbose_name='الحالة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'أمر بيع'
        verbose_name_plural = 'أوامر البيع'
        ordering = ['-date', '-order_number']
        permissions = [
            ('confirm_salesorder', 'تأكيد أمر بيع'),
            ('cancel_salesorder', 'إلغاء أمر بيع'),
            ('convert_salesorder', 'تحويل أمر بيع إلى فاتورة'),
        ]

    def __str__(self):
        return f'{self.order_number} - {self.customer.name}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = SequenceNumber.get_next_number('sales_order')
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return sum(quantize_10(line.line_total) for line in self.lines.all())

    @property
    def total_quantity(self):
        return sum(line.quantity for line in self.lines.all())

    def calculate_totals(self):
        return self.subtotal

    def remaining_to_invoice(self):
        return sum(
            (line.quantity - line.invoiced_quantity)
            for line in self.lines.all()
        )


class SalesOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE,
                              related_name='lines', verbose_name='أمر البيع')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='الكمية')
    unit_price = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                     verbose_name='سعر البيع')
    invoiced_quantity = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                            verbose_name='الكمية المفوترة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')

    class Meta:
        verbose_name = 'بند أمر بيع'
        verbose_name_plural = 'بنود أمر البيع'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    @property
    def line_total(self):
        return safe_mul(self.quantity, self.unit_price)

    @property
    def invoiced_total(self):
        return safe_mul(self.invoiced_quantity, self.unit_price)

    @property
    def remaining_quantity(self):
        return self.quantity - self.invoiced_quantity
