import uuid

from django.contrib.auth.models import User
from django.db import models

from budget.models import Budget, CostCenter
from common.decimal_utils import quantize_10, safe_mul
from common.models import SequenceNumber
from purchases.models import Product, Supplier


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('sent', 'مُرسل'),
        ('approved', 'معتمد'),
        ('received', 'مستلم'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, blank=True, verbose_name='رقم أمر الشراء')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='المورد')
    date = models.DateField(verbose_name='التاريخ')
    expected_date = models.DateField(blank=True, null=True, verbose_name='تاريخ التسليم المتوقع')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='مركز التكلفة'
    )
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'أمر شراء'
        verbose_name_plural = 'أوامر الشراء'
        ordering = ['-date', '-order_number']
        permissions = [
            ('approve_purchaseorder', 'اعتماد أمر شراء'),
            ('cancel_purchaseorder', 'إلغاء أمر شراء'),
            ('convert_purchaseorder', 'تحويل أمر شراء إلى فاتورة'),
        ]

    def __str__(self):
        return f'{self.order_number} - {self.supplier.name}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = SequenceNumber.get_next_number('purchase_order')
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return sum(quantize_10(line.line_total) for line in self.lines.all())

    @property
    def total_quantity(self):
        return sum(line.quantity for line in self.lines.all())

    def calculate_totals(self):
        """إعادة حساب إجماليات الأمر (للعرض فقط - لا تُخزَّن)."""
        return self.subtotal

    def remaining_to_receive(self):
        return sum((line.quantity - line.received_quantity) for line in self.lines.all())

    def budget_check(self):
        """فحص توفّر الميزانية لمركز التكلفة (القاعدة: أمر الشراء لا يتجاوز المتبقي من الموازنة المعتمدة)."""
        if not self.cost_center:
            return {'ok': True, 'available': None, 'message': 'لم يُحدَّد مركز تكلفة — لا يوجد قيد موازنة'}
        budgets = Budget.objects.filter(cost_center=self.cost_center, status='active')
        available = sum((b.budgeted_amount - b.actual_amount) for b in budgets)
        total = self.subtotal
        if total <= available:
            return {'ok': True, 'available': available, 'message': 'الطلب ضمن الموازنة المتاحة'}
        return {'ok': False, 'available': available, 'message': 'الطلب يتجاوز الموازنة المتاحة لمركز التكلفة'}


class PurchaseOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines', verbose_name='أمر الشراء')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='الكمية')
    unit_price = models.DecimalField(max_digits=20, decimal_places=10, default=0, verbose_name='سعر الوحدة')
    received_quantity = models.DecimalField(max_digits=20, decimal_places=10, default=0, verbose_name='الكمية المستلمة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')

    class Meta:
        verbose_name = 'بند أمر شراء'
        verbose_name_plural = 'بنود أمر الشراء'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    @property
    def line_total(self):
        return safe_mul(self.quantity, self.unit_price)

    @property
    def received_total(self):
        return safe_mul(self.received_quantity, self.unit_price)

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity
