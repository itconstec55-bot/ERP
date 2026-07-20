from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import User
from accounts.models import Account, JournalEntry
import uuid
from common.validators import (validate_positive_decimal, validate_vat_rate, 
                                validate_withholding_tax_type, validate_payment_method,
                                validate_non_negative_decimal)
from common.decimal_utils import (quantize_10, quantize_display, quantize_vat, calculate_vat,
                                   calculate_withholding, FinancialDecimal)


class Supplier(models.Model):
    SUPPLIER_TYPE_CHOICES = [
        ('company', 'شركة'),
        ('individual', 'فرد'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود المورد')
    name = models.CharField(max_length=200, verbose_name='اسم المورد')
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPE_CHOICES,
                                      default='company', verbose_name='نوع المورد')
    tax_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='الرقم الضريبي')
    commercial_register = models.CharField(max_length=50, blank=True, null=True, verbose_name='سجل تجاري')
    address = models.TextField(blank=True, null=True, verbose_name='العنوان')
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name='المدينة')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='التليفون')
    mobile = models.CharField(max_length=20, blank=True, null=True, verbose_name='المحمول')
    email = models.EmailField(blank=True, null=True, verbose_name='البريد الإلكتروني')
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name='الحساب المحاسبي')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='نشط')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')


    credit_limit = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                        verbose_name='حد الائتمان')
    current_balance = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                           verbose_name='الرصيد الحالي')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مورد'
        verbose_name_plural = 'الموردين'
        ordering = ['code']
        permissions = [
            ('view_supplier_list', 'عرض قائمة الموردين'),
            ('export_supplier', 'تصدير بيانات الموردين'),
        ]

    def __str__(self):
        return f'{self.code} - {self.name}'


class ProductCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود التصنيف')
    name = models.CharField(max_length=200, verbose_name='اسم التصنيف')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='children', verbose_name='التصنيف الأعلى')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تصنيف منتج'
        verbose_name_plural = 'تصنيفات المنتجات'
        ordering = ['code']

    def __str__(self):
        if self.parent:
            return f'{self.parent} / {self.name}'
        return self.name

    @property
    def is_leaf(self):
        return not self.children.exists()

    def get_ancestors(self):
        chain = []
        node = self.parent
        while node is not None:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def get_full_code(self):
        if self.parent:
            return f'{self.parent.get_full_code()}-{self.code}'
        return self.code


class UnitOfMeasure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود الوحدة')
    name = models.CharField(max_length=200, verbose_name='اسم الوحدة')
    symbol = models.CharField(max_length=20, blank=True, null=True, verbose_name='رمز الوحدة')
    base_unit = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='derived_units', verbose_name='الوحدة الأساسية')
    conversion_factor = models.DecimalField(max_digits=15, decimal_places=6, default=1,
                                            verbose_name='معامل التحويل للوحدة الأساسية')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'وحدة قياس'
        verbose_name_plural = 'وحدات القياس'
        ordering = ['code']

    def __str__(self):
        return f'{self.name}' + (f' ({self.symbol})' if self.symbol else '')

    def _base_factor(self):
        factor = self.conversion_factor or Decimal('1')
        node = self.base_unit
        while node is not None:
            factor *= (node.conversion_factor or Decimal('1'))
            node = node.base_unit
        return factor

    def to_base(self, quantity):
        """تحويل كمية من هذه الوحدة إلى الوحدة الأساسية."""
        return quantity * self._base_factor()

    def convert_to(self, quantity, target):
        """تحويل كمية من هذه الوحدة إلى وحدة هدف عبر الوحدة الأساسية."""
        if target is None or self.pk == target.pk:
            return quantity
        return self.to_base(quantity) / target._base_factor()

    @classmethod
    def convert(cls, quantity, from_unit, to_unit):
        if from_unit is None or to_unit is None:
            return quantity
        return from_unit.convert_to(quantity, to_unit)


class CatalogSettings(models.Model):
    """إعدادات الكتالوج (وحيدة): وحدات وتصنيفات افتراضية وخيارات إلزامية."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    default_unit = models.ForeignKey(UnitOfMeasure, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+',
                                     verbose_name='وحدة القياس الافتراضية')
    default_category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='+',
                                         verbose_name='التصنيف الافتراضي')
    enforce_unit = models.BooleanField(default=False, verbose_name='إلزام تحديد وحدة القياس')
    enforce_category = models.BooleanField(default=False, verbose_name='إلزام تحديد التصنيف')
    allow_decimal_quantity = models.BooleanField(default=True, verbose_name='السماح بكميات عشرية')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إعدادات الكتالوج'
        verbose_name_plural = 'إعدادات الكتالوج'

    def __str__(self):
        return 'إعدادات الكتالوج'

    def save(self, *args, **kwargs):
        if self._state.adding:
            # new object - check if any instance already exists
            if CatalogSettings.objects.exists():
                raise ValueError('إعدادات الكتالوج فريدة ولا يمكن تكرارها')
        else:
            # existing object - ensure we're not creating a duplicate by checking if another exists
            if CatalogSettings.objects.exclude(pk=self.pk).exists():
                raise ValueError('إعدادات الكتالوج فريدة ولا يمكن تكرارها')
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _created = cls.objects.get_or_create()
        return obj


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود المنتج')
    barcode = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name='الباركود')
    name = models.CharField(max_length=200, verbose_name='اسم المنتج')
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name='التصنيف')
    unit_of_measure = models.ForeignKey(UnitOfMeasure, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='products', verbose_name='وحدة القياس')
    description = models.TextField(blank=True, null=True, verbose_name='الوصف')
    unit = models.CharField(max_length=50, default='قطعة', verbose_name='وحدة القياس')
    purchase_price = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                          verbose_name='سعر الشراء')
    selling_price = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                         verbose_name='سعر البيع')
    current_stock = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                         verbose_name='المخزون الحالي')
    minimum_stock = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                                         verbose_name='الحد الأدنى للمخزون')
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=14,
                                    verbose_name='نسبة الضريبة')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'منتج'
        verbose_name_plural = 'المنتجات'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    @property
    def profit_margin(self):
        if self.purchase_price > 0:
            return ((self.selling_price - self.purchase_price) / self.purchase_price) * 100
        return 0

    @property
    def stock_value(self):
        return self.current_stock * self.purchase_price

    def save(self, *args, **kwargs):
        if self.unit_of_measure and self.unit != self.unit_of_measure.name:
            self.unit = self.unit_of_measure.name
        super().save(*args, **kwargs)


class PurchaseInvoice(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'نقدي'),
        ('credit', 'آجل'),
        ('check', 'شيك'),
        ('transfer', 'تحويل بنكي'),
    ]
    WITHHOLDING_TAX_CHOICES = [
        (0, 'بدون'),
        (1, '1% - شركات'),
        (3, '3% - جهات حكومية'),
        (5, '5% - مقاولات'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, verbose_name='رقم الفاتورة')
    file_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='رقم الملف', db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='المورد')
    date = models.DateField(verbose_name='التاريخ')
    due_date = models.DateField(blank=True, null=True, verbose_name='تاريخ الاستحقاق')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES,
                                       default='credit', verbose_name='طريقة الدفع',
                                       validators=[validate_payment_method])
    is_tax_invoice = models.BooleanField(default=True, verbose_name='فاتورة مؤثرة في الضرائب')
    withholding_tax_type = models.IntegerField(choices=WITHHOLDING_TAX_CHOICES, default=0,
                                                verbose_name='نسبة الخصم والتحصيل',
                                                validators=[validate_withholding_tax_type])
    subtotal = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                    verbose_name='المبلغ قبل الضريبة')
    vat_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                      verbose_name='ضريبة القيمة المضافة')
    discount_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                           verbose_name='الخصم على الفاتورة')
    withholding_tax_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                                  verbose_name='مبلغ الخصم والتحصيل')
    total_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                        verbose_name='الإجمالي')
    paid_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                       verbose_name='المبلغ المدفوع')
    remaining_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                            verbose_name='المبلغ المتبقي')
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                       verbose_name='القيد المحاسبي')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    currency = models.ForeignKey('currency.Currency', on_delete=models.PROTECT, null=True, blank=True, verbose_name='العملة')
    currency_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='المبلغ بالعملة')
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, default=1, verbose_name='سعر الصرف')
    is_posted = models.BooleanField(default=False, verbose_name='مرحل')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_purchases', verbose_name='معتمد بواسطة')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الاعتماد')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_approved(self):
        return self.approved_by_id is not None

    def approve(self, user):
        if self.is_posted:
            raise ValueError('لا يمكن اعتماد فاتورة مرحلة')
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=['approved_by', 'approved_at'])

    class Meta:
        verbose_name = 'فاتورة مشتريات'
        verbose_name_plural = 'فواتير المشتريات'
        ordering = ['-date', '-invoice_number']
        permissions = [
            ('approve_purchaseinvoice', 'اعتماد فاتورة مشتريات'),
            ('print_purchaseinvoice', 'طباعة فاتورة مشتريات'),
            ('export_purchaseinvoice', 'تصدير فواتير المشتريات'),
        ]
        indexes = [
            models.Index(fields=['supplier', '-date'], name='pi_supplier_date_idx'),
            models.Index(fields=['date', 'is_posted'], name='pi_date_posted_idx'),
            models.Index(fields=['invoice_number'], name='pi_number_idx'),
            models.Index(fields=['file_number'], name='pi_file_number_idx'),
            models.Index(fields=['payment_method', '-date'], name='pi_paymethod_date_idx'),
        ]

    def __str__(self):
        return f'{self.invoice_number} - {self.supplier.name}'

    def calculate_totals(self):
        from common.decimal_utils import quantize_10, quantize_vat, calculate_vat, calculate_withholding, safe_add, safe_sub
        lines = self.lines.all()
        self.subtotal = sum(quantize_10(line.total_price) for line in lines)
        if self.is_tax_invoice:
            self.vat_amount = calculate_vat(self.subtotal)
        else:
            self.vat_amount = Decimal('0')
        if self.withholding_tax_type > 0:
            self.withholding_tax_amount = calculate_withholding(self.subtotal, self.withholding_tax_type)
        else:
            self.withholding_tax_amount = Decimal('0')
        self.total_amount = safe_add(self.subtotal, self.vat_amount)
        self.total_amount = safe_sub(self.total_amount, self.discount_amount)
        self.remaining_amount = safe_sub(safe_sub(self.total_amount, self.paid_amount), self.withholding_tax_amount)
        self.save(update_fields=['subtotal', 'vat_amount', 'total_amount',
                                  'remaining_amount', 'discount_amount', 'withholding_tax_amount'])

    def create_journal_entry(self):
        from common.accounting_service import JournalEntryService
        from common.models import SequenceNumber
        from company.models import Company

        # قفل الصف لمنع الترحيل المزدوج (Race Condition)
        # بدون select_for_update، طلبان متزامنان يمكن أن ينشآن قيدين للفاتورة نفسها
        with transaction.atomic():
            locked_invoice = PurchaseInvoice.objects.select_for_update().get(pk=self.pk)
            if locked_invoice.is_posted and locked_invoice.journal_entry:
                return

            if not locked_invoice.is_approved:
                raise ValueError('يجب اعتماد الفاتورة قبل الترحيل')

            company = Company.get_company()

            # حل الحسابات
            purchases_account = company.purchases_account or JournalEntryService.get_account('1300')
            vat_account = company.vat_account or JournalEntryService.get_account('1350')
            supplier_account = locked_invoice.supplier.account or company.supplier_account or JournalEntryService.get_account('3100')
            withholding_account = company.withholding_tax_account or JournalEntryService.get_account('2130')
            discount_account = JournalEntryService.get_account('4300')

            lines = []

            # مدين: حساب المشتريات/المصروفات = المجموع الفرعي
            lines.append({
                'account': purchases_account,
                'debit': locked_invoice.subtotal, 'credit': Decimal('0'),
                'description': f'مشتريات - {locked_invoice.supplier.name}',
            })

            # مدين: ضريبة القيمة المضافة
            if locked_invoice.is_tax_invoice and locked_invoice.vat_amount > 0:
                lines.append({
                    'account': vat_account,
                    'debit': locked_invoice.vat_amount, 'credit': Decimal('0'),
                    'description': 'ضريبة القيمة المضافة المحصلة',
                })

            # دائن: حساب المورد (الصافي المستحق = الإجمالي - الخصم والتحصيل)
            net_payable = locked_invoice.total_amount - locked_invoice.withholding_tax_amount
            lines.append({
                'account': supplier_account,
                'debit': Decimal('0'), 'credit': net_payable,
                'description': f'المورد - {locked_invoice.supplier.name}',
            })

            # دائن: حساب الخصم والتحصيل المستحق للهيئة
            if locked_invoice.withholding_tax_amount > 0:
                lines.append({
                    'account': withholding_account,
                    'debit': Decimal('0'), 'credit': locked_invoice.withholding_tax_amount,
                    'description': f'الخصم والتحصيل {locked_invoice.get_withholding_tax_type_display()}',
                })

            # دائن: الخصم على الفاتورة (مقابل)
            if locked_invoice.discount_amount > 0:
                lines.append({
                    'account': discount_account,
                    'debit': Decimal('0'), 'credit': locked_invoice.discount_amount,
                    'description': f'خصم على فاتورة - {locked_invoice.supplier.name}',
                })

            entry_number = SequenceNumber.get_next_number('journal_entry')
            entry = JournalEntryService.create_entry(
                entry_type='purchase',
                date=locked_invoice.date,
                description=f'فاتورة مشتريات رقم {locked_invoice.invoice_number} من {locked_invoice.supplier.name}',
                reference=locked_invoice.invoice_number,
                file_number=locked_invoice.file_number,
                lines=lines,
                created_by=locked_invoice.created_by,
                entry_number=entry_number,
            )

            # تحديث رصيد المورد (مدين علينا بإجمالي الفاتورة)
            supplier = Supplier.objects.select_for_update().get(pk=locked_invoice.supplier_id)
            supplier.current_balance += locked_invoice.total_amount
            supplier.save(update_fields=['current_balance'])

            locked_invoice.journal_entry = entry
            locked_invoice.is_posted = True
            locked_invoice.save(update_fields=['journal_entry', 'is_posted'])
            self.journal_entry = entry
            self.is_posted = True


class PurchaseInvoiceLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE,
                                 related_name='lines', verbose_name='الفاتورة')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='المنتج')
    quantity = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='الكمية',
                                    validators=[validate_positive_decimal])
    unit_price = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='سعر الوحدة',
                                      validators=[validate_positive_decimal])
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                             verbose_name='نسبة الخصم')
    total_price = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                       verbose_name='الإجمالي')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'بند فاتورة مشتريات'
        verbose_name_plural = 'بنود فواتير المشتريات'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    def save(self, *args, **kwargs):
        from common.decimal_utils import quantize_10, safe_mul, safe_sub, safe_div
        self.total_price = safe_mul(self.quantity, self.unit_price)
        if self.discount_percent > 0:
            discount_amount = safe_mul(self.total_price, safe_div(self.discount_percent, Decimal('100')))
            self.total_price = safe_sub(self.total_price, discount_amount)
        super().save(*args, **kwargs)
        # ملاحظة: إجماليات الفاتورة يتم تحديثها من خلال formset.save() في الـ view
        # لا نستدعي calculate_totals() هنا لتجنب مشكلة N+1