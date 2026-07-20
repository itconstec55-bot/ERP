import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class ConcreteMixDesign(models.Model):
    """
    تصميم خلطة الخرسانة - يحدد النسب والمكونات الأساسية
    مثل: C25/30, C30/37, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField('كود الخلطة', max_length=50, unique=True)
    name = models.CharField('اسم الخلطة', max_length=200)
    strength_class = models.CharField('فئة القوة', max_length=50, help_text='مثال: C25/30, C30/37')
    slump_cm = models.DecimalField('الانهيار (سم)', max_digits=6, decimal_places=2, help_text='قيمة الانهيار بالسنتيمتر')
    max_aggregate_mm = models.DecimalField('حجم أقصى للركام (مم)', max_digits=6, decimal_places=2, default=20)
    water_cement_ratio = models.DecimalField('نسبة الماء/الأسمنت', max_digits=5, decimal_places=3, help_text='نسبة وسطرة الماء للأسمنت')
    target_strength_mpa = models.DecimalField('قوة الهدف (ميجاباسكال)', max_digits=8, decimal_places=2, help_text='قوة الضغط المطلوبة بعد 28 يوم')
    description = models.TextField('الوصف', blank=True)
    is_active = models.BooleanField('نشط', default=True)
    cost_per_m3 = models.DecimalField('التكلفة للمتر المكعب', max_digits=15, decimal_places=6, default=0)
    selling_price_per_m3 = models.DecimalField('سعر البيع للمتر المكعب', max_digits=15, decimal_places=6, default=0)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)
    product = models.ForeignKey(
        'purchases.Product', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='المنتج المقابل في المخزون',
        help_text='يُستخدم عند إنشاء فاتورة مبيعات تلقائية لتسليم الخرسانة'
    )

    class Meta:
        verbose_name = 'تصميم خلطة الخرسانة'
        verbose_name_plural = 'تصاميم خلطات الخرسانة'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name} ({self.strength_class})'

    @property
    def total_weight_per_m3(self):
        return sum(c.quantity_kg for c in self.components.all())

    def calculate_cost(self):
        from decimal import Decimal
        total = Decimal('0')
        for comp in self.components.select_related('product').all():
            if comp.product and comp.product.purchase_price:
                total += comp.quantity_kg * comp.product.purchase_price / Decimal('1000')
        self.cost_per_m3 = total
        self.save(update_fields=['cost_per_m3'])
        return total


class MixComponent(models.Model):
    """
    مكونات الخلطة - نسب المواد لكل متر مكعب
    """
    COMPONENT_TYPES = [
        ('cement', 'أسمنت'),
        ('fine_aggregate', 'ركام ناعم (رمل)'),
        ('coarse_aggregate', 'ركام خشن (كحلاوي)'),
        ('water', 'ماء'),
        ('ad_additive', 'مدھات كيميائية'),
        ('fly_ash', 'رماد طائر'),
        ('slag', 'خامل محطم'),
        ('fiber', 'ألياف'),
        ('other', 'أخرى'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mix_design = models.ForeignKey(ConcreteMixDesign, on_delete=models.CASCADE, related_name='components', verbose_name='تصميم الخلطة')
    component_type = models.CharField('نوع المكون', max_length=20, choices=COMPONENT_TYPES)
    name = models.CharField('اسم المكون', max_length=200)
    quantity_kg = models.DecimalField('الكمية (كجم/م³)', max_digits=10, decimal_places=3)
    product = models.ForeignKey(
        'purchases.Product', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='المنتج المقابل',
        help_text='المنتج في نظام المخزون المقابل لهذا المكون'
    )
    order = models.PositiveIntegerField('ترتيب العرض', default=0)

    class Meta:
        verbose_name = 'مكون الخلطة'
        verbose_name_plural = 'مكونات الخلطة'
        ordering = ['order', 'component_type']
        unique_together = ['mix_design', 'component_type', 'name']

    def __str__(self):
        return f'{self.name}: {self.quantity_kg} كجم/م³'

    @property
    def cost_per_kg(self):
        if self.product and self.product.purchase_price:
            return self.product.purchase_price / Decimal('1000')
        return Decimal('0')


class CustomerRequest(models.Model):
    """
    طلب العميل - أول مرحلة في دورة الطلب
    """
    STATUS_CHOICES = [
        ('new', 'جديد'),
        ('confirmed', 'مؤكد'),
        ('in_production', 'قيد الإنتاج'),
        ('delivered', 'تم التسليم'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_number = models.CharField('رقم الطلب', max_length=50, unique=True)
    customer = models.ForeignKey(
        'sales.Customer', on_delete=models.PROTECT, verbose_name='العميل'
    )
    project_name = models.CharField('اسم المشروع', max_length=300)
    site_address = models.TextField('عنوان الموقع')
    contact_person = models.CharField('جهة الاتصال', max_length=200, blank=True)
    contact_phone = models.CharField('هاتف الاتصال', max_length=50, blank=True)
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='new')
    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة'
    )

    class Meta:
        verbose_name = 'طلب عميل'
        verbose_name_plural = 'طلبات العملاء'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['customer']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.request_number} - {self.customer.name}'

    def save(self, *args, **kwargs):
        if not self.request_number:
            from common.auto_number import generate_auto_number
            self.request_number = generate_auto_number('CR', CustomerRequest)
        super().save(*args, **kwargs)


class ProductionOrder(models.Model):
    """
    أمر الإنتاج - يرتبط بطلب العميل ويحدد الخلطة والكمية
    """
    PRIORITY_CHOICES = [
        ('normal', 'عادي'),
        ('urgent', 'عاجل'),
        ('very_urgent', 'عاجل جداً'),
    ]
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('scheduled', 'مجدول'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField('رقم أمر الإنتاج', max_length=50, unique=True)
    customer_request = models.ForeignKey(
        CustomerRequest, on_delete=models.PROTECT, verbose_name='طلب العميل',
        related_name='production_orders'
    )
    mix_design = models.ForeignKey(
        ConcreteMixDesign, on_delete=models.PROTECT, verbose_name='تصميم الخلطة'
    )
    quantity_m3 = models.DecimalField('الكمية المطلوبة (م³)', max_digits=10, decimal_places=3)
    quantity_delivered = models.DecimalField('الكمية المسلمة (م³)', max_digits=10, decimal_places=3, default=0)
    priority = models.CharField('الأولوية', max_length=20, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_date = models.DateField('تاريخ الجدولة', null=True, blank=True)
    scheduled_time_from = models.TimeField('من الساعة', null=True, blank=True)
    scheduled_time_to = models.TimeField('إلى الساعة', null=True, blank=True)
    pump_required = models.BooleanField('يتطلب مضخة', default=False)
    pump_cost = models.DecimalField('تكلفة المضخة', max_digits=12, decimal_places=6, default=0)
    special_requirements = models.TextField('متطلبات خاصة', blank=True)
    unit_price = models.DecimalField('سعر الوحدة', max_digits=15, decimal_places=6, default=0)
    total_price = models.DecimalField('الإجمالي', max_digits=18, decimal_places=6, default=0)
    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة'
    )
    sales_invoice = models.ForeignKey(
        'sales.SalesInvoice', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='production_orders', verbose_name='فاتورة المبيعات المولّدة',
        help_text='تُنشأ تلقائياً عند اكتمال تسليم الخرسانة'
    )
    branch = models.ForeignKey(
        'company.CompanyBranch', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='الفرع', help_text='يُستخدم للصلاحيات على مستوى الكائن'
    )

    class Meta:
        verbose_name = 'أمر إنتاج'
        verbose_name_plural = 'أوامر الإنتاج'
        ordering = ['-created_at']
        permissions = [
            ('approve_productionorder', 'اعتماد أمر إنتاج'),
            ('print_productionorder', 'طباعة أمر إنتاج'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['scheduled_date']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f'{self.order_number} - {self.customer_request.customer.name}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            from common.auto_number import generate_auto_number
            self.order_number = generate_auto_number('PO', ProductionOrder)
        self.total_price = self.quantity_m3 * self.unit_price
        super().save(*args, **kwargs)
        if self.status == 'completed' and not self.sales_invoice_id:
            try:
                self.generate_sales_invoice()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    'تعذر إنشاء فاتورة المبيعات لأمر الإنتاج %s: %s', self.order_number, e
                )

    def generate_sales_invoice(self, created_by=None):
        """ينشئ فاتورة مبيعات تلقائية لتسليم أمر الإنتاج المكتمل."""
        if self.sales_invoice_id:
            return self.sales_invoice
        from common.auto_number import generate_auto_number
        from sales.models import SalesInvoice, SalesInvoiceLine
        customer = self.customer_request.customer
        product = self.mix_design.product or None
        if not product:
            from purchases.models import Product
            product = Product.objects.filter(
                name__icontains='خرسانة'
            ).first()
        if not customer or not product:
            return None
        invoice = SalesInvoice.objects.create(
            invoice_number=generate_auto_number('SI', SalesInvoice),
            customer=customer,
            date=timezone.now().date(),
            is_tax_invoice=True,
            created_by=created_by,
            production_order=self,
            branch=self.branch,
        )
        SalesInvoiceLine.objects.create(
            invoice=invoice,
            product=product,
            quantity=self.quantity_m3,
            unit_price=self.unit_price,
            cost_price=product.purchase_price or Decimal('0'),
        )
        invoice.calculate_totals()
        try:
            invoice.create_journal_entry()
        except Exception:
            pass
        self.sales_invoice = invoice
        self.sales_invoice_id = invoice.pk
        super().save(update_fields=['sales_invoice'])
        return invoice

    @property
    def remaining_quantity(self):
        return self.quantity_m3 - self.quantity_delivered

    @property
    def completion_percentage(self):
        if self.quantity_m3 == 0:
            return 0
        return (self.quantity_delivered / self.quantity_m3) * 100

    def clean(self):
        if self.quantity_delivered > self.quantity_m3:
            raise ValidationError('الكمية المسلمة لا يمكن أن تتجاوز الكمية المطلوبة')


class Truck(models.Model):
    """
    الشاحنات - أسطول نقل الخرسانة
    """
    CAPACITY_CHOICES = [
        (6, '6 م³'),
        (7, '7 م³'),
        (8, '8 م³'),
        (9, '9 م³'),
        (10, '10 م³'),
        (12, '12 م³'),
    ]
    STATUS_CHOICES = [
        ('available', 'متاحة'),
        ('on_route', 'في الطريق'),
        ('delivering', 'قيد التسليم'),
        ('returning', 'عائدة'),
        ('maintenance', 'صيانة'),
        ('out_of_service', 'خارج الخدمة'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plate_number = models.CharField('رقم اللوحة', max_length=50, unique=True)
    driver_name = models.CharField('اسم السائق', max_length=200)
    driver_phone = models.CharField('هاتف السائق', max_length=50)
    capacity_m3 = models.PositiveIntegerField('السعة (م³)', choices=CAPACITY_CHOICES, default=8)
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='available')
    current_lat = models.DecimalField('خط العرض الحالي', max_digits=10, decimal_places=7, null=True, blank=True)
    current_lng = models.DecimalField('خط الطول الحالي', max_digits=10, decimal_places=7, null=True, blank=True)
    is_active = models.BooleanField('نشط', default=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)

    class Meta:
        verbose_name = 'شاحنة'
        verbose_name_plural = 'الشاحنات'
        ordering = ['plate_number']

    def __str__(self):
        return f'{self.plate_number} - {self.driver_name}'

    @property
    def is_available(self):
        return self.status == 'available' and self.is_active


class ProductionBatch(models.Model):
    """
    الدفعة الإنتاجية - كل محاولة خلط وتسليم
    """
    STATUS_CHOICES = [
        ('queued', 'في الطابور'),
        ('mixing', 'جاري الخلط'),
        ('loading', 'جاري التحميل'),
        ('in_transit', 'في الطريق'),
        ('pouring', 'جاري الصب'),
        ('completed', 'مكتمل'),
        ('returned', 'مرتجع'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_number = models.CharField('رقم الدفعة', max_length=50, unique=True)
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, verbose_name='أمر الإنتاج',
        related_name='batches'
    )
    truck = models.ForeignKey(
        Truck, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الشاحنة'
    )
    quantity_m3 = models.DecimalField('الكمية (م³)', max_digits=10, decimal_places=3)
    actual_quantity_m3 = models.DecimalField('الكمية الفعلية (م³)', max_digits=10, decimal_places=3, default=0)
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='queued')
    mixing_time = models.DateTimeField('وقت الخلط', null=True, blank=True)
    departure_time = models.DateTimeField('وقت المغادرة', null=True, blank=True)
    arrival_time = models.DateTimeField('وقت الوصول', null=True, blank=True)
    pouring_start = models.DateTimeField('بداية الصب', null=True, blank=True)
    pouring_end = models.DateTimeField('نهاية الصب', null=True, blank=True)
    returned_quantity_m3 = models.DecimalField('الكمية المرتجعة (م³)', max_digits=10, decimal_places=3, default=0)
    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)

    class Meta:
        verbose_name = 'دفعة إنتاجية'
        verbose_name_plural = 'الدفعات الإنتاجية'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.batch_number} - {self.production_order.order_number}'

    def save(self, *args, **kwargs):
        if not self.batch_number:
            from common.auto_number import generate_auto_number
            self.batch_number = generate_auto_number('B', ProductionBatch)
        super().save(*args, **kwargs)

    @property
    def transit_duration(self):
        if self.departure_time and self.arrival_time:
            return self.arrival_time - self.departure_time
        return None

    @property
    def pouring_duration(self):
        if self.pouring_start and self.pouring_end:
            return self.pouring_end - self.pouring_start
        return None


class DeliverySchedule(models.Model):
    """
    جدول التسليمات - تتبع جدولة الشاحنات ووقت التسليم
    """
    STATUS_CHOICES = [
        ('scheduled', 'مجدول'),
        ('confirmed', 'مؤكد'),
        ('en_route', 'في الطريق'),
        ('delivered', 'تم التسليم'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, verbose_name='أمر الإنتاج',
        related_name='delivery_schedules'
    )
    batch = models.ForeignKey(
        ProductionBatch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الدفعة'
    )
    delivery_date = models.DateField('تاريخ التسليم')
    time_slot_from = models.TimeField('من الساعة')
    time_slot_to = models.TimeField('إلى الساعة')
    truck = models.ForeignKey(
        Truck, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الشاحنة'
    )
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='scheduled')
    sequence = models.PositiveIntegerField('الترتيب', default=1)
    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)

    class Meta:
        verbose_name = 'جدول تسليم'
        verbose_name_plural = 'جداول التسليم'
        ordering = ['delivery_date', 'time_slot_from']
        indexes = [
            models.Index(fields=['delivery_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.production_order.order_number} - {self.delivery_date}'

    def clean(self):
        if self.time_slot_from and self.time_slot_to:
            if self.time_slot_from >= self.time_slot_to:
                raise ValidationError('وقت البداية يجب أن يكون قبل وقت النهاية')

        # فحص تعارض الشاحنة
        if self.truck_id:
            overlapping = DeliverySchedule.objects.filter(
                truck=self.truck,
                delivery_date=self.delivery_date,
                time_slot_from__lt=self.time_slot_to,
                time_slot_to__gt=self.time_slot_from,
                status__in=['scheduled', 'confirmed', 'en_route'],
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError('الشاحنة محجوزة في هذا الوقت')


class ProductionCost(models.Model):
    """
    تكاليف الإنتاج - ربط تكاليف المواد والتشغيل بأوامر الإنتاج
    """
    COST_TYPES = [
        ('materials', 'مواد أولية'),
        ('labor', 'أجور عمال'),
        ('transport', 'نقل'),
        ('fuel', 'وقود'),
        ('maintenance', 'صيانة'),
        ('equipment', 'معدات'),
        ('other', 'أخرى'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, verbose_name='أمر الإنتاج',
        related_name='costs'
    )
    cost_type = models.CharField('نوع التكلفة', max_length=20, choices=COST_TYPES)
    amount = models.DecimalField('المبلغ', max_digits=15, decimal_places=6)
    description = models.CharField('الوصف', max_length=300, blank=True)
    journal_entry = models.ForeignKey(
        'accounts.JournalEntry', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='القيد المحاسبي'
    )
    date = models.DateField('التاريخ', default=timezone.now)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        verbose_name = 'تكلفة إنتاج'
        verbose_name_plural = 'تكاليف الإنتاج'
        ordering = ['-date']

    def __str__(self):
        return f'{self.get_cost_type_display()} - {self.amount}'


class Silo(models.Model):
    """
    سيلة الاسمنت - تتبع كميات الاسمنت المتوفرة والحد الأدنى للطلب
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('اسم السيلة', max_length=200)
    code = models.CharField('كود السيلة', max_length=50, unique=True)
    capacity_tons = models.DecimalField('السعة الطاقة (طن)', max_digits=10, decimal_places=2)
    current_stock_tons = models.DecimalField('المخزون الحالي (طن)', max_digits=10, decimal_places=2, default=0)
    minimum_order_tons = models.DecimalField('الحد الأدنى للطلب (طن)', max_digits=10, decimal_places=2, default=0)
    critical_level_tons = models.DecimalField('الحد الحرج (طن)', max_digits=10, decimal_places=2, default=0)
    location = models.CharField('الموقع', max_length=300, blank=True)
    cement_type = models.CharField('نوع الاسمنت', max_length=100, blank=True, help_text='مثال: CEM I, CEM II')
    supplier = models.ForeignKey(
        'purchases.Supplier', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='المورد الأساسي'
    )
    is_active = models.BooleanField('نشط', default=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)

    class Meta:
        verbose_name = 'سيلة اسمنت'
        verbose_name_plural = 'السيلو'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    @property
    def fill_percentage(self):
        if self.capacity_tons == 0:
            return 0
        return float((self.current_stock_tons / self.capacity_tons) * 100)

    @property
    def status(self):
        if self.current_stock_tons <= self.critical_level_tons:
            return 'critical'
        if self.current_stock_tons <= self.minimum_order_tons:
            return 'low'
        return 'ok'

    @property
    def needs_reorder(self):
        return self.current_stock_tons <= self.minimum_order_tons

    @property
    def tons_to_order(self):
        if self.needs_reorder:
            return self.capacity_tons - self.current_stock_tons
        return 0


class SiloTransaction(models.Model):
    """
    حركات السيلة - تتبع التوريد والاستهلاك
    """
    TRANSACTION_TYPES = [
        ('in', 'توريد'),
        ('out', 'استهلاك'),
        ('adjustment', 'تسوية'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    silo = models.ForeignKey(Silo, on_delete=models.CASCADE, verbose_name='السيلة', related_name='transactions')
    transaction_type = models.CharField('نوع الحركة', max_length=20, choices=TRANSACTION_TYPES)
    quantity_tons = models.DecimalField('الكمية (طن)', max_digits=10, decimal_places=3)
    previous_stock = models.DecimalField('المخزون السابق (طن)', max_digits=10, decimal_places=3, default=0)
    new_stock = models.DecimalField('المخزون الجديد (طن)', max_digits=10, decimal_places=3, default=0)
    reference_number = models.CharField('رقم المرجع', max_length=100, blank=True)
    notes = models.TextField('ملاحظات', blank=True)
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='أمر الإنتاج المرتبط'
    )
    date = models.DateTimeField('التاريخ', default=timezone.now)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة'
    )

    class Meta:
        verbose_name = 'حركة سيلة'
        verbose_name_plural = 'حركات السيلو'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['silo']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return f'{self.silo.code} - {self.get_transaction_type_display()} - {self.quantity_tons} طن'

    def save(self, *args, **kwargs):
        if self._state.adding:
            from django.db import transaction
            with transaction.atomic():
                # قفل صف السيلة أثناء القراءة-التعديل-الكتابة لمنع سباق التحديثات
                # المتزامنة (Lost Update) عند تسجيل حركات متعددة على نفس السيلة.
                silo = Silo.objects.select_for_update().get(pk=self.silo_id)
                self.previous_stock = silo.current_stock_tons
                if self.transaction_type == 'in':
                    self.new_stock = self.previous_stock + self.quantity_tons
                elif self.transaction_type == 'out':
                    self.new_stock = self.previous_stock - self.quantity_tons
                else:
                    self.new_stock = self.quantity_tons
                silo.current_stock_tons = self.new_stock
                silo.save(update_fields=['current_stock_tons', 'updated_at'])
                self.silo = silo
        super().save(*args, **kwargs)
