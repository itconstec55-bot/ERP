import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models, transaction
from django.utils import timezone

from accounts.models import Account, JournalEntry
from common.models import SequenceNumber
from common.validators import (
    validate_non_negative_decimal,
    validate_payment_method,
    validate_positive_decimal,
    validate_withholding_tax_type,
)


class Customer(models.Model):
    CUSTOMER_TYPE_CHOICES = [('company', 'شركة'), ('individual', 'فرد'), ('government', 'جهة حكومية')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='كود العميل')
    name = models.CharField(max_length=200, verbose_name='اسم العميل')
    customer_type = models.CharField(
        max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='company', verbose_name='نوع العميل'
    )
    tax_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='الرقم الضريبي')
    commercial_register = models.CharField(max_length=50, blank=True, null=True, verbose_name='سجل تجاري')
    address = models.TextField(blank=True, null=True, verbose_name='العنوان')
    country = models.CharField(max_length=100, blank=True, null=True, default='EG', verbose_name='الدولة')
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name='المدينة')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='التليفون')
    mobile = models.CharField(max_length=20, blank=True, null=True, verbose_name='المحمول')
    email = models.EmailField(blank=True, null=True, verbose_name='البريد الإلكتروني')
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الحساب المحاسبي'
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='نشط')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    credit_limit = models.DecimalField(max_digits=20, decimal_places=10, default=0, verbose_name='حد الائتمان')
    current_balance = models.DecimalField(max_digits=20, decimal_places=10, default=0, verbose_name='الرصيد الحالي')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'عميل'
        verbose_name_plural = 'العملاء'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class SalesInvoice(models.Model):
    PAYMENT_METHOD_CHOICES = [('cash', 'نقدي'), ('credit', 'آجل'), ('check', 'شيك'), ('transfer', 'تحويل بنكي')]
    WITHHOLDING_TAX_CHOICES = [(0, 'بدون'), (1, '1% - شركات'), (3, '3% - جهات حكومية'), (5, '5% - مقاولات')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, verbose_name='رقم الفاتورة')
    file_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='رقم الملف', db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name='العميل')
    date = models.DateField(verbose_name='التاريخ')
    due_date = models.DateField(blank=True, null=True, verbose_name='تاريخ الاستحقاق')
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='credit',
        verbose_name='طريقة الدفع',
        validators=[validate_payment_method],
    )
    is_tax_invoice = models.BooleanField(default=True, verbose_name='فاتورة مؤثرة في الضرائب')
    withholding_tax_type = models.IntegerField(
        choices=WITHHOLDING_TAX_CHOICES,
        default=0,
        verbose_name='نسبة الخصم والتحصيل',
        validators=[validate_withholding_tax_type],
    )
    subtotal = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        verbose_name='المبلغ قبل الضريبة',
        validators=[validate_positive_decimal],
    )
    vat_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        verbose_name='ضريبة القيمة المضافة',
        validators=[validate_positive_decimal],
    )
    discount_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        verbose_name='الخصم على الفاتورة',
        validators=[validate_non_negative_decimal],
    )
    withholding_tax_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        verbose_name='مبلغ الخصم والتحصيل',
        validators=[validate_positive_decimal],
    )
    total_amount = models.DecimalField(
        max_digits=30, decimal_places=10, default=0, verbose_name='الإجمالي', validators=[validate_positive_decimal]
    )
    paid_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        verbose_name='المبلغ المحصّل',
        validators=[validate_non_negative_decimal],
    )
    remaining_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        verbose_name='المبلغ المتبقي',
        validators=[validate_positive_decimal],
    )
    cost_of_goods = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        verbose_name='تكلفة البضاعة',
        validators=[validate_positive_decimal],
    )
    gross_profit = models.DecimalField(
        max_digits=30, decimal_places=10, default=0, verbose_name='إجمالي الربح', validators=[validate_positive_decimal]
    )
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القيد المحاسبي'
    )
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    currency = models.ForeignKey(
        'currency.Currency', on_delete=models.PROTECT, null=True, blank=True, verbose_name='العملة'
    )
    currency_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0, verbose_name='المبلغ بالعملة')
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, default=1, verbose_name='سعر الصرف')
    is_posted = models.BooleanField(default=False, verbose_name='مرحل')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_sales',
        verbose_name='معتمد بواسطة',
    )
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

    production_order = models.ForeignKey(
        'concrete_production.ProductionOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_invoices',
        verbose_name='أمر إنتاج الخرسانة',
        help_text='يرتبط تلقائياً عند إنشاء فاتورة من تسليم خرسانة',
    )
    branch = models.ForeignKey(
        'company.CompanyBranch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='الفرع',
        help_text='يُستخدم للصلاحيات على مستوى الكائن',
    )

    class Meta:
        verbose_name = 'فاتورة مبيعات'
        verbose_name_plural = 'فواتير المبيعات'
        ordering = ['-date', '-invoice_number']
        permissions = [
            ('approve_salesinvoice', 'اعتماد فاتورة مبيعات'),
            ('print_salesinvoice', 'طباعة فاتورة مبيعات'),
            ('export_salesinvoice', 'تصدير فواتير المبيعات'),
        ]
        indexes = [
            models.Index(fields=['customer', '-date'], name='si_customer_date_idx'),
            models.Index(fields=['date', 'is_posted'], name='si_date_posted_idx'),
            models.Index(fields=['invoice_number'], name='si_number_idx'),
            models.Index(fields=['file_number'], name='si_file_number_idx'),
            models.Index(fields=['payment_method', '-date'], name='si_paymethod_date_idx'),
        ]

    def __str__(self):
        return f'{self.invoice_number} - {self.customer.name}'

    def calculate_totals(self):
        from common.decimal_utils import calculate_vat, calculate_withholding, quantize_10, safe_add, safe_sub

        lines = self.lines.all()
        self.subtotal = sum(quantize_10(line.total_price) for line in lines)
        self.cost_of_goods = sum(quantize_10(line.cost_total) for line in lines)
        VAT_RATE = Decimal('0.14')
        if self.is_tax_invoice:
            self.vat_amount = calculate_vat(self.subtotal, VAT_RATE)
        else:
            self.vat_amount = Decimal('0')
        if self.withholding_tax_type > 0:
            self.withholding_tax_amount = calculate_withholding(self.subtotal, self.withholding_tax_type)
        else:
            self.withholding_tax_amount = 0
        self.total_amount = safe_add(self.subtotal, self.vat_amount)
        self.total_amount = safe_sub(self.total_amount, self.discount_amount)
        self.remaining_amount = safe_sub(safe_sub(self.total_amount, self.paid_amount), self.withholding_tax_amount)
        self.gross_profit = safe_sub(self.subtotal, self.cost_of_goods)
        self.save(
            update_fields=[
                'subtotal',
                'vat_amount',
                'total_amount',
                'remaining_amount',
                'discount_amount',
                'withholding_tax_amount',
                'cost_of_goods',
                'gross_profit',
            ]
        )

    def create_journal_entry(self):
        from common.accounting_service import JournalEntryService
        from company.models import Company
        from warehouses.models import StockMovement, Warehouse, WarehouseProduct

        company = Company.get_company()

        with transaction.atomic():
            invoice = SalesInvoice.objects.select_for_update().get(pk=self.pk)
            if invoice.is_posted:
                raise ValueError('الفاتورة مرحلة بالفعل')
            if not invoice.is_approved:
                raise ValueError('يجب اعتماد الفاتورة قبل الترحيل')

            entry_number = SequenceNumber.get_next_number('journal_entry')
            entry = JournalEntry.objects.create(
                entry_number=entry_number,
                entry_type='sale',
                date=invoice.date,
                description=f'فاتورة مبيعات رقم {invoice.invoice_number} للعميل {invoice.customer.name}',
                reference=invoice.invoice_number,
                file_number=invoice.file_number,
                created_by=invoice.created_by,
            )

            # الحسابات
            customer_account = (
                invoice.customer.account or company.customer_account or JournalEntryService.get_account('1100')
            )
            revenue_account = company.sales_revenue_account or JournalEntryService.get_account('4100')
            vat_account = company.vat_account or JournalEntryService.get_account('3200')
            # حساب الخصم والتحصيل المستحق للغير (مدين = مدين للشركة من جهة الخصم)
            withholding_receivable_account = company.withholding_tax_account or JournalEntryService.get_account('1140')
            # حساب الخصم على المبيعات (مقابل الإيراد - دائن)
            discount_account = JournalEntryService.get_account('4101')

            # القيد المتوازن:
            #   مدين العميل (الصافي) = الإجمالي - الخصم والتحصيل
            #   مدين الخصم والتحصيل = مبلغ الخصم والتحصيل (إن وُجد)
            #   دائن الإيرادات = المجموع الفرعي
            #   دائن ضريبة القيمة المضافة = ضريبة القيمة المضافة (إن وُجدت)
            #   دائن الخصم على المبيعات = مبلغ الخصم على الفاتورة (إن وُجد)
            net_receivable = invoice.total_amount - invoice.withholding_tax_amount
            entry.lines.create(
                account=customer_account,
                debit=net_receivable,
                credit=0,
                description=f'العميل - {invoice.customer.name}',
            )
            if invoice.withholding_tax_amount > 0:
                entry.lines.create(
                    account=withholding_receivable_account,
                    debit=invoice.withholding_tax_amount,
                    credit=0,
                    description=f'الخصم والتحصيل {invoice.get_withholding_tax_type_display()}',
                )
            entry.lines.create(
                account=revenue_account,
                debit=0,
                credit=invoice.subtotal,
                description=f'إيرادات مبيعات - {invoice.customer.name}',
            )
            if invoice.is_tax_invoice and invoice.vat_amount > 0:
                entry.lines.create(
                    account=vat_account, debit=0, credit=invoice.vat_amount, description='ضريبة القيمة المضافة المستحقة'
                )
            if invoice.discount_amount > 0:
                entry.lines.create(
                    account=discount_account, debit=0, credit=invoice.discount_amount, description='خصم على الفاتورة'
                )

            entry.calculate_totals()
            entry.post()
            invoice.journal_entry = entry
            invoice.is_posted = True
            invoice.save(update_fields=['journal_entry', 'is_posted'])
            self.journal_entry = entry
            self.is_posted = True

            # تحديث رصيد العميل (المبلغ الإجمالي المستحق)
            customer = invoice.customer
            customer.current_balance = (customer.current_balance or 0) + invoice.total_amount
            customer.save(update_fields=['current_balance'])

            # إنشاء حركات صادر للمخزون وتخفيض أرصدة المخازن لكل بند مع تطبيق FIFO
            for line in invoice.lines.select_related('product').all():
                wp = WarehouseProduct.objects.filter(product=line.product).order_by('-quantity').first()
                warehouse = wp.warehouse if wp else Warehouse.objects.first()
                if not warehouse:
                    continue

                # حساب التكلفة باستخدام FIFO
                try:
                    unit_cost, total_cost = SalesInvoiceLine.get_fifo_cost(line.product, line.quantity)
                except Exception:
                    unit_cost = line.cost_price
                    total_cost = line.cost_price * line.quantity

                StockMovement.objects.create(
                    movement_number=f'SM-{invoice.invoice_number}-{line.product.code}-{uuid.uuid4().hex[:6]}',
                    movement_type='out',
                    warehouse=warehouse,
                    product=line.product,
                    quantity=line.quantity,
                    unit_cost=unit_cost,
                    reference_number=invoice.invoice_number,
                    date=invoice.date,
                    performed_by=invoice.created_by,
                )
                if wp:
                    wp.quantity = (wp.quantity or 0) - line.quantity
                    wp.save(update_fields=['quantity'])


class SalesInvoiceLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name='lines', verbose_name='الفاتورة')
    product = models.ForeignKey('purchases.Product', on_delete=models.PROTECT, verbose_name='المنتج')
    quantity = models.DecimalField(
        max_digits=20, decimal_places=10, verbose_name='الكمية', validators=[validate_positive_decimal]
    )
    unit_price = models.DecimalField(
        max_digits=20, decimal_places=10, verbose_name='سعر البيع', validators=[validate_positive_decimal]
    )
    cost_price = models.DecimalField(
        max_digits=20, decimal_places=10, default=0, verbose_name='سعر الشراء', validators=[validate_positive_decimal]
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الخصم', validators=[validate_positive_decimal]
    )
    total_price = models.DecimalField(
        max_digits=30, decimal_places=10, default=0, verbose_name='الإجمالي', validators=[validate_positive_decimal]
    )
    cost_total = models.DecimalField(
        max_digits=30, decimal_places=10, default=0, verbose_name='التكلفة', validators=[validate_positive_decimal]
    )
    profit = models.DecimalField(
        max_digits=30, decimal_places=10, default=0, verbose_name='الربح', validators=[validate_positive_decimal]
    )
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الربح %')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'بند فاتورة مبيعات'
        verbose_name_plural = 'بنود فواتير المبيعات'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} - {self.quantity}'

    def save(self, *args, **kwargs):
        from common.decimal_utils import safe_div, safe_mul, safe_sub

        if self.cost_price == 0 and self.product:
            self.cost_price = self.product.purchase_price
        self.total_price = safe_mul(self.quantity, self.unit_price)
        if self.discount_percent > 0:
            discount_amount = safe_mul(self.total_price, safe_div(self.discount_percent, 100))
            self.total_price = safe_sub(self.total_price, discount_amount)
        self.cost_total = safe_mul(self.quantity, self.cost_price)
        self.profit = safe_sub(self.total_price, self.cost_total)
        if self.total_price > 0:
            self.profit_margin = safe_mul(safe_div(self.profit, self.total_price), 100)
        else:
            self.profit_margin = 0
        super().save(*args, **kwargs)

    @classmethod
    def get_fifo_cost(cls, product, quantity):
        """حساب تكلفة FIFO للكمية المطلوبة."""

        from warehouses.models import InventoryCostLayer, WarehouseProduct

        wp = WarehouseProduct.objects.filter(product=product).order_by('-quantity').first()
        if not wp:
            return product.purchase_price, product.purchase_price * quantity
        unit_cost, total_cost = InventoryCostLayer.consume_fifo(
            product=product, warehouse=wp.warehouse, quantity=quantity
        )
        return unit_cost, total_cost
