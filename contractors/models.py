import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from accounts.models import Account, JournalEntry


class Contractor(models.Model):
    """
    المقاول - كيان رئيسي يمثل المقاول/الشركة المقاولة
    """
    CONTRACTOR_TYPES = [
        ('company', 'شركة'),
        ('individual', 'فرد'),
        ('government', 'جهة حكومية'),
    ]
    STATUS_CHOICES = [
        ('active', 'نشط'),
        ('suspended', 'معلق'),
        ('blacklisted', 'محظور'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField('كود المقاول', max_length=50, unique=True)
    name = models.CharField('اسم المقاول', max_length=300)
    contractor_type = models.CharField('النوع', max_length=20, choices=CONTRACTOR_TYPES, default='company')
    tax_number = models.CharField('الرقم الضريبي', max_length=50, blank=True)
    commercial_register = models.CharField('رقم السجل التجاري', max_length=50, blank=True)
    phone = models.CharField('الهاتف', max_length=50)
    email = models.EmailField('البريد الإلكتروني', blank=True)
    address = models.TextField('العنوان', blank=True)
    speciality = models.CharField('التخصص', max_length=200, blank=True, help_text='مثال: أعمال هيكلية، كهرباء، سباكة')
    credit_limit = models.DecimalField('حد الائتمان', max_digits=20, decimal_places=10, default=0)
    current_balance = models.DecimalField('الرصيد الحالي', max_digits=20, decimal_places=10, default=0)
    retention_rate = models.DecimalField('نسبة الاحتفاظ', max_digits=5, decimal_places=2, default=5,
                                         help_text='نسبة الاحتفاظ من كل مستخلص %')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='active')
    is_active = models.BooleanField('نشط', default=True)
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='الحساب المحاسبي',
        help_text='حساب المقاول في دليل الحسابات'
    )
    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)

    class Meta:
        verbose_name = 'مقاول'
        verbose_name_plural = 'المقاولون'
        ordering = ['code']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f'{self.code} - {self.name}'

    @property
    def total_contracts(self):
        return self.contracts.count()

    @property
    def active_contracts_count(self):
        return self.contracts.filter(status__in=['active', 'in_progress']).count()

    @property
    def total_certificates_amount(self):
        from django.db.models import Sum
        result = self.contracts.aggregate(
            total=Sum('certificates__net_amount')
        )
        return result['total'] or Decimal('0')

    @property
    def total_payments_amount(self):
        from django.db.models import Sum
        result = ContractorPayment.objects.filter(
            contract__contractor=self
        ).aggregate(total=Sum('amount'))
        return result['total'] or Decimal('0')

    @property
    def outstanding_amount(self):
        return self.total_certificates_amount - self.total_payments_amount


class Contract(models.Model):
    """
    العقد - يربط المقاول بمجموعة أعمال مع شروط دفع وجدول تسليم
    """
    CONTRACT_TYPES = [
        ('lump_sum', 'مبلغ مقطوع'),
        ('unit_price', 'أسعارunità'),
        ('cost_plus', 'التكلفة + ربح'),
        ('time_material', 'وقت + مواد'),
    ]
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('pending_approval', 'قيد الموافقة'),
        ('active', 'نشط'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('closed', 'مغلق'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract_number = models.CharField('رقم العقد', max_length=50, unique=True)
    title = models.CharField('عنوان العقد', max_length=300)
    contractor = models.ForeignKey(
        Contractor, on_delete=models.PROTECT, verbose_name='المقاول',
        related_name='contracts'
    )
    contract_type = models.CharField('نوع العقد', max_length=20, choices=CONTRACT_TYPES, default='lump_sum')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='draft')

    # المبالغ المالية
    contract_amount = models.DecimalField('قيمة العقد', max_digits=20, decimal_places=10, default=0)
    vat_rate = models.DecimalField('نسبة الضريبة', max_digits=5, decimal_places=2, default=14)
    vat_amount = models.DecimalField('مبلغ الضريبة', max_digits=20, decimal_places=10, default=0)
    total_with_vat = models.DecimalField('الإجمالي شامل الضريبة', max_digits=20, decimal_places=10, default=0)

    # التواريخ
    signing_date = models.DateField('تاريخ التوقيع', null=True, blank=True)
    start_date = models.DateField('تاريخ البداية', null=True, blank=True)
    end_date = models.DateField('تاريخ النهاية', null=True, blank=True)
    actual_end_date = models.DateField('تاريخ النهاية الفعلي', null=True, blank=True)

    # الشروط
    retention_rate = models.DecimalField('نسبة الاحتفاظ', max_digits=5, decimal_places=2, default=5)
    advance_payment_percent = models.DecimalField('نسبة الدفعة المقدمة', max_digits=5, decimal_places=2, default=0)
    advance_payment_amount = models.DecimalField('قيمة الدفعة المقدمة', max_digits=20, decimal_places=10, default=0)
    penalties_clause = models.TextField('شروط الغرامات', blank=True)
    special_conditions = models.TextField('شروط خاصة', blank=True)

    # التقدم
    completion_percentage = models.DecimalField('نسبة الإنجاز', max_digits=5, decimal_places=2, default=0)
    total_certified = models.DecimalField('إجمالي المستخلصات', max_digits=20, decimal_places=10, default=0)
    total_paid = models.DecimalField('إجمالي المدفوعات', max_digits=20, decimal_places=10, default=0)
    total_retained = models.DecimalField('إجمالي المحتجز', max_digits=20, decimal_places=10, default=0)

    # الحساب المحاسبي
    cost_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='حساب تكاليف العقد',
        help_text='حساب تكلفة الأعمال في دليل الحسابات'
    )

    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة'
    )

    class Meta:
        verbose_name = 'عقد'
        verbose_name_plural = 'العقود'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['contractor']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['start_date']),
        ]

    def __str__(self):
        return f'{self.contract_number} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.contract_number:
            from common.auto_number import generate_auto_number
            self.contract_number = generate_auto_number('CTR', Contract)
        self.vat_amount = self.contract_amount * self.vat_rate / Decimal('100')
        self.total_with_vat = self.contract_amount + self.vat_amount
        super().save(*args, **kwargs)

    def calculate_totals(self):
        from django.db.models import Sum
        cert_totals = self.certificates.aggregate(
            certified=Sum('gross_amount'),
            retained=Sum('retention_amount'),
            paid=Sum('paid_amount'),
        )
        self.total_certified = cert_totals['certified'] or Decimal('0')
        self.total_retained = cert_totals['retained'] or Decimal('0')
        self.total_paid = cert_totals['paid'] or Decimal('0')
        if self.contract_amount > 0:
            self.completion_percentage = (self.total_certified / self.contract_amount) * Decimal('100')
        self.save(update_fields=[
            'total_certified', 'total_retained', 'total_paid', 'completion_percentage'
        ])

    @property
    def remaining_amount(self):
        return self.contract_amount - self.total_certified

    @property
    def outstanding_balance(self):
        return self.total_certified - self.total_paid


class ContractItem(models.Model):
    """
    بنود العقد - بنود الأعمال والكميات والأسعار
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, verbose_name='العقد',
        related_name='items'
    )
    item_number = models.CharField('رقم البند', max_length=20)
    description = models.TextField('وصف البند')
    unit = models.CharField('الوحدة', max_length=50, default='م³')
    quantity = models.DecimalField('الكمية', max_digits=20, decimal_places=10, default=0)
    unit_price = models.DecimalField('سعر الوحدة', max_digits=20, decimal_places=10, default=0)
    total_price = models.DecimalField('الإجمالي', max_digits=30, decimal_places=10, default=0)
    executed_quantity = models.DecimalField('الكمية المنفذة', max_digits=20, decimal_places=10, default=0)
    order = models.PositiveIntegerField('الترتيب', default=0)

    class Meta:
        verbose_name = 'بند العقد'
        verbose_name_plural = 'بنود العقد'
        ordering = ['order', 'item_number']

    def __str__(self):
        return f'{self.item_number} - {self.description[:50]}'

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    @property
    def execution_percentage(self):
        if self.quantity == 0:
            return 0
        return (self.executed_quantity / self.quantity) * Decimal('100')


class InterimCertificate(models.Model):
    """
    المستخلص - فاتورة تقدم أعمال
    """
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('submitted', 'مقدم'),
        ('approved', 'موافق عليه'),
        ('certified', 'معتمد'),
        ('paid', 'مدفوع'),
        ('rejected', 'مرفوض'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate_number = models.CharField('رقم المستخلص', max_length=50, unique=True)
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, verbose_name='العقد',
        related_name='certificates'
    )
    period_number = models.PositiveIntegerField('فترة المستخلص', help_text='رقم الفترة الزمنية')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='draft')

    # المبالغ
    gross_amount = models.DecimalField('المبلغ الإجمالي', max_digits=20, decimal_places=10, default=0)
    previous_amount = models.DecimalField('المبلغ السابق', max_digits=20, decimal_places=10, default=0)
    current_amount = models.DecimalField('المبلغ الحالي', max_digits=20, decimal_places=10, default=0)
    retention_amount = models.DecimalField('مبلغ الاحتفاظ', max_digits=20, decimal_places=10, default=0)
    advance_deduction = models.DecimalField('خصم الدفعة المقدمة', max_digits=20, decimal_places=10, default=0)
    vat_amount = models.DecimalField('الضريبة', max_digits=20, decimal_places=10, default=0)
    net_amount = models.DecimalField('المبلغ الصافي', max_digits=20, decimal_places=10, default=0)
    paid_amount = models.DecimalField('المبلغ المدفوع', max_digits=20, decimal_places=10, default=0)

    # التواريخ
    period_from = models.DateField('من تاريخ')
    period_to = models.DateField('إلى تاريخ')
    submission_date = models.DateField('تاريخ التقديم', null=True, blank=True)
    approval_date = models.DateField('تاريخ الموافقة', null=True, blank=True)
    payment_date = models.DateField('تاريخ الدفع', null=True, blank=True)

    # المحاسبي
    is_posted = models.BooleanField('تم الترحيل', default=False)
    journal_entry = models.ForeignKey(
        'accounts.JournalEntry', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='القيد المحاسبي'
    )

    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة'
    )

    class Meta:
        verbose_name = 'مستخلص'
        verbose_name_plural = 'المستخلصات'
        ordering = ['-created_at']
        permissions = [
            ('approve_interimcertificate', 'اعتماد مستخلص'),
            ('print_interimcertificate', 'طباعة مستخلص'),
            ('export_interimcertificate', 'تصدير المستخلصات'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['contract']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.certificate_number} - {self.contract.contract_number}'

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            from common.auto_number import generate_auto_number
            self.certificate_number = generate_auto_number('IC', InterimCertificate)
        super().save(*args, **kwargs)

    def calculate_totals(self):
        self.gross_amount = self.previous_amount + self.current_amount
        contract = self.contract
        retention_rate = contract.retention_rate / Decimal('100')
        self.retention_amount = self.gross_amount * retention_rate

        if contract.advance_payment_percent > 0:
            adv_rate = contract.advance_payment_percent / Decimal('100')
            self.advance_deduction = self.current_amount * adv_rate

        vat_rate = contract.vat_rate / Decimal('100')
        taxable = self.gross_amount - self.retention_amount - self.advance_deduction
        self.vat_amount = taxable * vat_rate
        self.net_amount = taxable + self.vat_amount

        self.save()

    def clean(self):
        if self.previous_amount < 0:
            raise ValidationError('المبلغ السابق لا يمكن أن يكون سالباً')
        if self.current_amount < 0:
            raise ValidationError('المبلغ الحالي لا يمكن أن يكون سالباً')

    def create_journal_entry(self):
        """
        ربط المستخلص بالقيود المحاسبية
        مدين: تكاليف الأعمال (حساب العقد)
        دائن: مستحقات المقاول (حساب المقاول)
        """
        if self.is_posted and self.journal_entry:
            return
        from common.accounting_service import JournalEntryService
        from company.models import Company
        self.refresh_from_db()
        company = Company.get_company()
        contractor = self.contract.contractor

        with transaction.atomic():
            entry = JournalEntry.objects.create(
                entry_type='purchase',
                date=self.approval_date or timezone.now().date(),
                description=f'مستخلص رقم {self.certificate_number} - {contractor.name}',
                reference=self.certificate_number,
                entry_number=self.certificate_number,
                created_by=self.created_by,
            )

            # مدين: تكاليف الأعمال
            cost_account = self.contract.cost_account or JournalEntryService.get_account('5100')
            entry.lines.create(
                account=cost_account,
                debit=self.net_amount, credit=0,
                description=f'تكاليف أعمال - {self.contract.title}',
            )

            # دائن: مستحقات المقاول
            contractor_account = contractor.account or company.supplier_account or JournalEntryService.get_account('3100')
            entry.lines.create(
                account=contractor_account,
                debit=0, credit=self.net_amount,
                description=f'مستحقات المقاول - {contractor.name}',
            )

            entry.calculate_totals()
            entry.post()
            self.journal_entry = entry
            self.is_posted = True
            self.save(update_fields=['journal_entry', 'is_posted'])


class CertificateItem(models.Model):
    """
    بنود المستخلص - تفاصيل التنفيذ لكل بند
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate = models.ForeignKey(
        InterimCertificate, on_delete=models.CASCADE, verbose_name='المستخلص',
        related_name='items'
    )
    contract_item = models.ForeignKey(
        ContractItem, on_delete=models.PROTECT, verbose_name='بند العقد',
        related_name='certificate_items'
    )
    previous_quantity = models.DecimalField('الكمية السابقة', max_digits=20, decimal_places=10, default=0)
    current_quantity = models.DecimalField('الكمية الحالية', max_digits=20, decimal_places=10, default=0)
    total_executed = models.DecimalField('الإجمالي المنفذ', max_digits=20, decimal_places=10, default=0)
    amount = models.DecimalField('المبلغ', max_digits=20, decimal_places=10, default=0)

    class Meta:
        verbose_name = 'بند مستخلص'
        verbose_name_plural = 'بنود المستخلص'
        ordering = ['contract_item__order']

    def __str__(self):
        return f'{self.contract_item.item_number}: {self.current_quantity}'

    def save(self, *args, **kwargs):
        self.total_executed = self.previous_quantity + self.current_quantity
        self.amount = self.current_quantity * self.contract_item.unit_price
        super().save(*args, **kwargs)


class ContractorPayment(models.Model):
    """
    دفعة للمقاول - تتبع المدفوعات
    """
    PAYMENT_METHODS = [
        ('cash', 'نقدي'),
        ('bank_transfer', 'تحويل بنكي'),
        ('check', 'شيك'),
        ('advance', 'دفعة مقدمة'),
        ('retention_release', 'إفراج عن محتجز'),
    ]
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('paid', 'مدفوع'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_number = models.CharField('رقم الدفعة', max_length=50, unique=True)
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, verbose_name='العقد',
        related_name='payments'
    )
    certificate = models.ForeignKey(
        InterimCertificate, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='المستخلص المرتبط'
    )
    amount = models.DecimalField('المبلغ', max_digits=20, decimal_places=10)
    payment_method = models.CharField('طريقة الدفع', max_length=20, choices=PAYMENT_METHODS, default='bank_transfer')
    payment_date = models.DateField('تاريخ الدفع')
    check_number = models.CharField('رقم الشيك', max_length=50, blank=True)
    bank_reference = models.CharField('مرجع التحويل', max_length=100, blank=True)
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='draft')

    # المحاسبي
    is_posted = models.BooleanField('تم الترحيل', default=False)
    journal_entry = models.ForeignKey(
        'accounts.JournalEntry', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='القيد المحاسبي'
    )
    # المرجع المالي
    safe_transaction = models.ForeignKey(
        'treasury.SafeTransaction', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='حركة الخزينة'
    )

    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)
    updated_at = models.DateTimeField('تاريخ التعديل', auto_now=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة'
    )

    class Meta:
        verbose_name = 'دفعة مقاول'
        verbose_name_plural = 'مدفوعات المقاولين'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['contract']),
            models.Index(fields=['-payment_date']),
        ]

    def __str__(self):
        return f'{self.payment_number} - {self.contract.contractor.name} - {self.amount}'

    def save(self, *args, **kwargs):
        if not self.payment_number:
            from common.auto_number import generate_auto_number
            self.payment_number = generate_auto_number('CP', ContractorPayment)
        super().save(*args, **kwargs)

    def create_journal_entry(self):
        """
        ربط الدفعة بالقيود المحاسبية
        مدين: مستحقات المقاول (تقليل الدين)
        دائن: الخزينة / البنك (خروج المبلغ)
        """
        if self.is_posted and self.journal_entry:
            return
        from common.accounting_service import JournalEntryService
        from company.models import Company
        self.refresh_from_db()
        company = Company.get_company()
        contractor = self.contract.contractor

        with transaction.atomic():
            entry = JournalEntry.objects.create(
                entry_type='payment',
                date=self.payment_date,
                description=f'دفعة للمقاول {contractor.name} - {self.payment_number}',
                reference=self.payment_number,
                entry_number=self.payment_number,
                created_by=self.created_by,
            )

            # مدين: مستحقات المقاول (تقليل الدين)
            contractor_account = contractor.account or company.supplier_account or JournalEntryService.get_account('3100')
            entry.lines.create(
                account=contractor_account,
                debit=self.amount, credit=0,
                description=f'دفعة للمقاول - {contractor.name}',
            )

            # دائن: الخزينة / البنك
            bank_account = JournalEntryService.get_account('1100')  # حساب البنك الافتراضي
            entry.lines.create(
                account=bank_account,
                debit=0, credit=self.amount,
                description=f'دفعة للمقاول {contractor.name}',
            )

            entry.calculate_totals()
            entry.post()
            self.journal_entry = entry
            self.is_posted = True
            self.save(update_fields=['journal_entry', 'is_posted'])

            # تحديث إجمالي المدفوعات في العقد
            self.contract.calculate_totals()
