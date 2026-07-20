from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
import uuid


class StockAdjustment(models.Model):
    TYPE_CHOICES = [
        ('addition', 'إضافة'),
        ('deduction', 'خصم'),
        ('count', 'جرد فعلي'),
    ]
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment_number = models.CharField(max_length=50, unique=True, verbose_name='رقم الجرد')
    date = models.DateField(verbose_name='التاريخ')
    adjustment_type = models.CharField(max_length=15, choices=TYPE_CHOICES, verbose_name='نوع الجرد')
    warehouse = models.ForeignKey('warehouses.Warehouse', on_delete=models.CASCADE, verbose_name='المخزن')
    reason = models.TextField(blank=True, null=True, verbose_name='سبب التعديل')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تعديل مخزون'
        verbose_name_plural = 'تعديلات المخزون'
        ordering = ['-date']

    def __str__(self):
        return f'{self.adjustment_number} - {self.get_adjustment_type_display()}'

    def approve(self):
        if self.status == 'approved':
            return
        from django.db import transaction
        with transaction.atomic():
            for line in self.lines.select_related('product').all():
                wp, created = self.warehouse.products.get_or_create(
                    product=line.product, defaults={'quantity': Decimal('0')}
                )
                if self.adjustment_type == 'addition':
                    wp.quantity += line.quantity
                elif self.adjustment_type == 'deduction':
                    if wp.quantity < line.quantity:
                        raise ValueError(
                            f'لا يوجد مخزون كافٍ للمنتج {line.product} (المتاح {wp.quantity})'
                        )
                    wp.quantity -= line.quantity
                elif self.adjustment_type == 'count':
                    wp.quantity = line.quantity
                wp.save()
            self.status = 'approved'
            self.save(update_fields=['status'])


class StockAdjustmentLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment = models.ForeignKey(StockAdjustment, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey('purchases.Product', on_delete=models.PROTECT, verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='الكمية')
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='المخزون الحالي')
    notes = models.CharField(max_length=200, blank=True, verbose_name='ملاحظات')

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'
