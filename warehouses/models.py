import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from purchases.models import Product


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود المخزن')
    name = models.CharField(max_length=200, verbose_name='اسم المخزن')
    location = models.CharField(max_length=300, blank=True, null=True, verbose_name='الموقع')
    manager = models.CharField(max_length=200, blank=True, null=True, verbose_name='مدير المخزن')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='التليفون')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مخزن'
        verbose_name_plural = 'المخازن'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class WarehouseProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE,
                                   related_name='products', verbose_name='المخزن')
    product = models.ForeignKey(Product, on_delete=models.PROTECT,
                                 related_name='warehouse_stock', verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                    verbose_name='الكمية الحالية')
    minimum_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                            verbose_name='الحد الأدنى')
    maximum_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                            verbose_name='الحد الأقصى')
    last_count_date = models.DateField(blank=True, null=True, verbose_name='آخر جرد')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'منتج في المخزن'
        verbose_name_plural = 'منتجات المخازن'
        unique_together = ['warehouse', 'product']
        ordering = ['warehouse', 'product']

    def __str__(self):
        return f'{self.warehouse.name} - {self.product.name} ({self.quantity})'

    @property
    def is_low(self):
        return self.quantity <= self.minimum_quantity and self.minimum_quantity > 0


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'وارد'),
        ('out', 'صادر'),
        ('transfer', 'تحويل'),
        ('adjustment', 'تسوية'),
        ('return_in', 'مرتجع وارد'),
        ('return_out', 'مرتجع صادر'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    movement_number = models.CharField(max_length=50, unique=True, verbose_name='رقم الحركة')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES, verbose_name='نوع الحركة')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE,
                                   related_name='movements', verbose_name='المخزن')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='incoming_movements', verbose_name='المخزن المحول إليه')
    product = models.ForeignKey(Product, on_delete=models.PROTECT,
                                 related_name='stock_movements', verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='الكمية')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='تكلفة الوحدة')
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                      verbose_name='التكلفة الإجمالية')
    reference_number = models.CharField(max_length=100, blank=True, null=True,
                                         verbose_name='رقم المرجع')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                      verbose_name='نفّذ الحركة')
    date = models.DateField(verbose_name='التاريخ')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'حركة مخزون'
        verbose_name_plural = 'حركات المخزون'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['warehouse', '-date'], name='sm_wh_date_idx'),
            models.Index(fields=['product', '-date'], name='sm_prod_date_idx'),
            models.Index(fields=['movement_type', '-date'], name='sm_type_date_idx'),
        ]
        permissions = [
            ('export_stockmovement', 'تصدير حركات المخزون'),
        ]

    def __str__(self):
        return f'{self.movement_number} - {self.get_movement_type_display()} - {self.product.name}'

    def save(self, *args, **kwargs):
        self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)


class InventoryCostLayer(models.Model):
    """طبقة تكلفة FIFO — تتبع كل دفعة شراء بسعرها الخاص."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT,
                                 related_name='cost_layers', verbose_name='المنتج')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE,
                                   related_name='cost_layers', verbose_name='المخزن')
    reference_number = models.CharField(max_length=100, blank=True, null=True,
                                         verbose_name='رقم المرجع')
    quantity_remaining = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                              verbose_name='الكمية المتبقية')
    unit_cost = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                     verbose_name='تكلفة الوحدة')
    total_cost = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                      verbose_name='التكلفة الإجمالية')
    date = models.DateField(verbose_name='التاريخ')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'طبقة تكلفة مخزون'
        verbose_name_plural = 'طبقات تكلفة المخزون'
        ordering = ['date', 'created_at']
        indexes = [
            models.Index(fields=['product', 'warehouse', 'is_active'], name='icl_prod_wh_idx'),
        ]

    def __str__(self):
        return f'{self.product.name} - {self.unit_cost} ({self.quantity_remaining})'

    def save(self, *args, **kwargs):
        self.total_cost = self.quantity_remaining * self.unit_cost
        super().save(*args, **kwargs)

    @classmethod
    def consume_fifo(cls, product, warehouse, quantity, reference_number=None, date=None):
        """استهلاك كمية من المخزون بأسلوب FIFO."""
        from django.utils import timezone
        if date is None:
            date = timezone.now().date()
        remaining = Decimal(str(quantity))
        total_cost = Decimal('0')
        layers = cls.objects.select_for_update().filter(
            product=product, warehouse=warehouse, is_active=True,
            quantity_remaining__gt=0
        ).order_by('date', 'created_at')

        for layer in layers:
            if remaining <= 0:
                break
            if layer.quantity_remaining >= remaining:
                layer.quantity_remaining -= remaining
                total_cost += remaining * layer.unit_cost
                if layer.quantity_remaining == 0:
                    layer.is_active = False
                layer.save(update_fields=['quantity_remaining', 'total_cost', 'is_active'])
                remaining = Decimal('0')
            else:
                total_cost += layer.quantity_remaining * layer.unit_cost
                remaining -= layer.quantity_remaining
                layer.quantity_remaining = Decimal('0')
                layer.is_active = False
                layer.save(update_fields=['quantity_remaining', 'total_cost', 'is_active'])

        if remaining > 0:
            avg_cost = total_cost / (quantity - remaining) if (quantity - remaining) > 0 else Decimal('0')
            total_cost += remaining * avg_cost

        avg_unit_cost = total_cost / quantity if quantity > 0 else Decimal('0')
        return avg_unit_cost, total_cost

    @classmethod
    def add_layer(cls, product, warehouse, quantity, unit_cost, reference_number=None, date=None):
        """إضافة طبقة تكلفة جديدة (عند الشراء/الاستلام)."""
        from django.utils import timezone
        if date is None:
            date = timezone.now().date()
        return cls.objects.create(
            product=product,
            warehouse=warehouse,
            quantity_remaining=quantity,
            unit_cost=unit_cost,
            reference_number=reference_number,
            date=date,
        )
