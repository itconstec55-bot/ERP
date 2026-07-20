from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
import uuid

from purchases.models import Supplier, Product
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from common.models import SequenceNumber
from common.decimal_utils import quantize_10, safe_mul


class GoodsReceivedNote(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكد'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn_number = models.CharField(max_length=50, unique=True, blank=True,
                                  verbose_name='رقم إيصال الاستلام')
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='goods_received_notes', verbose_name='أمر الشراء')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.PROTECT,
                                  null=True, blank=True, verbose_name='المستودع')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='المورد')
    date = models.DateField(verbose_name='التاريخ')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft',
                              verbose_name='الحالة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إيصال استلام بضاعة'
        verbose_name_plural = 'إيصالات استلام البضاعة'
        ordering = ['-date', '-grn_number']
        permissions = [
            ('confirm_goodsreceivednote', 'تأكيد إيصال استلام'),
            ('convert_goodsreceivednote', 'تحويل إيصال استلام إلى فاتورة'),
        ]

    def __str__(self):
        return f'{self.grn_number} - {self.supplier.name}'

    def save(self, *args, **kwargs):
        if not self.grn_number:
            self.grn_number = SequenceNumber.get_next_number('goods_received')
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return sum(quantize_10(line.line_total) for line in self.lines.all())

    def calculate_totals(self):
        return self.subtotal


class GoodsReceivedLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn = models.ForeignKey(GoodsReceivedNote, on_delete=models.CASCADE,
                            related_name='lines', verbose_name='إيصال الاستلام')
    purchase_order_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='goods_received_lines', verbose_name='بند أمر الشراء')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='المنتج')
    quantity_received = models.DecimalField(max_digits=20, decimal_places=2, verbose_name='الكمية المستلمة')
    unit_price = models.DecimalField(max_digits=20, decimal_places=2, default=0,
                                     verbose_name='سعر الوحدة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')

    class Meta:
        verbose_name = 'بند استلام بضاعة'
        verbose_name_plural = 'بنود استلام البضاعة'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity_received}'

    @property
    def line_total(self):
        return safe_mul(self.quantity_received, self.unit_price)
