import uuid
from django.db import models


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='اسم الشركة')
    name_en = models.CharField(max_length=200, blank=True, verbose_name='الاسم بالإنجليزية')
    address = models.TextField(blank=True, verbose_name='العنوان')
    city = models.CharField(max_length=100, blank=True, verbose_name='المدينة')
    country = models.CharField(max_length=100, default='مصر', verbose_name='الدولة')
    phone = models.CharField(max_length=20, blank=True, verbose_name='الهاتف')
    mobile = models.CharField(max_length=20, blank=True, verbose_name='المحمول')
    fax = models.CharField(max_length=20, blank=True, verbose_name='الفاكس')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    tax_number = models.CharField(max_length=50, blank=True, verbose_name='الرقم الضريبي')
    commercial_register = models.CharField(max_length=50, blank=True, verbose_name='السجل التجاري')
    company_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الشركة')
    logo = models.ImageField(upload_to='company logos/', blank=True, null=True, verbose_name='شعار الشركة')
    currency = models.CharField(max_length=10, default='ج.م', verbose_name='العملة')
    currency_code = models.CharField(max_length=10, default='EGP', verbose_name='كود العملة')
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=14, verbose_name='نسبة VAT %')
    fiscal_year_start = models.CharField(max_length=5, default='01-01', verbose_name='بداية السنة المالية')
    fiscal_year_end = models.CharField(max_length=5, default='12-31', verbose_name='نهاية السنة المالية')
    bank_name = models.CharField(max_length=200, blank=True, verbose_name='اسم البنك')
    bank_account_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الحساب البنكي')
    bank_iban = models.CharField(max_length=50, blank=True, verbose_name='IBAN')
    bank_swift = models.CharField(max_length=20, blank=True, verbose_name='SWIFT Code')
    registration_notes = models.TextField(blank=True, verbose_name='ملاحظات التسجيل')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # حسابات محاسبية افتراضية
    purchases_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='حساب المشتريات'
    )
    vat_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='حساب ضريبة القيمة المضافة'
    )
    withholding_tax_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='حساب الخصم والتحصيل'
    )
    supplier_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='حساب الموردين الافتراضي'
    )
    customer_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='حساب العملاء الافتراضي'
    )
    sales_revenue_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='حساب إيرادات المبيعات'
    )
    cogs_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='حساب تكلفة البضاعة المباعة'
    )
    inventory_account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='حساب المخزون'
    )

    class Meta:
        verbose_name = 'الشركة'
        verbose_name_plural = 'الشركات'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.pk and Company.objects.exists():
            raise ValueError('يمكن إنشاء شركة واحدة فقط')
        super().save(*args, **kwargs)

    @classmethod
    def get_company(cls):
        company = cls.objects.first()
        if not company:
            company = cls.objects.create(
                name='شركة تواريدات للتجارة',
                name_en='Tawaredat Trading Company',
                address='القاهرة، مصر',
                phone='01000000000',
                tax_number='123456789',
                currency='ج.م',
                currency_code='EGP',
                vat_rate=14,
            )
        return company


class CompanyBranch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='branches', verbose_name='الشركة')
    name = models.CharField(max_length=200, verbose_name='اسم الفرع')
    address = models.TextField(blank=True, verbose_name='العنوان')
    city = models.CharField(max_length=100, blank=True, verbose_name='المدينة')
    phone = models.CharField(max_length=20, blank=True, verbose_name='الهاتف')
    manager = models.CharField(max_length=100, blank=True, verbose_name='المدير')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    is_default = models.BooleanField(default=False, verbose_name='الفرع الرئيسي')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فرع'
        verbose_name_plural = 'الفروع'

    def __str__(self):
        return f'{self.company.name} - {self.name}'
