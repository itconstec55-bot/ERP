"""
نماذج الفاتورة الضريبية الإلكترونية (فاتورة)
التكامل مع منظومة الفاتورة الإلكترونية لـ مصلحة الضرائب المصرية (ETA)
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class ETAConnection(models.Model):
    """
    إعدادات الاتصال بمنظومة الفاتورة الإلكترونية (ETA)
    يحتوي على بيانات الاعتماد (client_id / client_secret) وبيئة التشغيل
    """
    ENVIRONMENT_CHOICES = [
        ('sandbox', 'بيئة الاختبار (Sandbox)'),
        ('production', 'بيئة الإنتاج (Production)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default='الافتراضي', verbose_name='اسم الإعداد')
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES,
                                   default='sandbox', verbose_name='بيئة التشغيل')
    client_id = models.CharField(max_length=255, blank=True, null=True, verbose_name='Client ID')
    client_secret = models.CharField(max_length=255, blank=True, null=True, verbose_name='Client Secret')
    # شهادة التوقيع الرقمي (PKI) — مسار الملف على الخادم
    certificate_path = models.CharField(max_length=500, blank=True, null=True,
                                        verbose_name='مسار شهادة التوقيع')
    certificate_password = models.CharField(max_length=255, blank=True, null=True,
                                            verbose_name='كلمة سر الشهادة')
    is_active = models.BooleanField(default=True, verbose_name='مفعل', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إعداد اتصال الضرائب'
        verbose_name_plural = 'إعدادات اتصال الضرائب'
        ordering = ['-is_active', '-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_environment_display()})'

    @property
    def base_url(self):
        if self.environment == 'production':
            return 'https://api.invoicing.eta.gov.eg/api'
        return 'https://api.preprod.invoicing.eta.gov.eg/api'

    @property
    def portal_url(self):
        if self.environment == 'production':
            return 'https://invoicing.eta.gov.eg'
        return 'https://preprod.invoicing.eta.gov.eg'


class TaxInvoice(models.Model):
    """
    الفاتورة الضريبية المرسلة لمنظومة الفاتورة الإلكترونية
    تُنشأ مرتبطة بفاتورة مبيعات موجودة، وتُرسل لمصلحة الضرائب
    """
    DOCUMENT_TYPE_CHOICES = [
        ('i', 'فاتورة مبيعات (Issued)'),
        ('c', 'إشعار دائن (Credit)'),
        ('d', 'إشعار مدين (Debit)'),
        ('s', 'فاتورة مرتجع (Summary)'),
    ]

    SUBMISSION_STATUS_CHOICES = [
        ('pending', 'في الانتظار'),
        ('submitting', 'جارٍ الإرسال'),
        ('submitted', 'تم الإرسال'),
        ('valid', 'صالحة (مقبولة)'),
        ('invalid', 'غير صالحة (مرفوضة)'),
        ('failed', 'فشل الإرسال'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # الرقم الداخلي للفاتورة الضريبية في النظام
    tax_invoice_number = models.CharField(max_length=50, unique=True, verbose_name='رقم الفاتورة الضريبية')
    sales_invoice = models.ForeignKey('sales.SalesInvoice', on_delete=models.PROTECT,
                                      related_name='tax_invoices', verbose_name='فاتورة المبيعات',
                                      blank=True, null=True)
    connection = models.ForeignKey(ETAConnection, on_delete=models.PROTECT,
                                   related_name='tax_invoices', verbose_name='إعداد الاتصال')
    document_type = models.CharField(max_length=1, choices=DOCUMENT_TYPE_CHOICES,
                                     default='i', verbose_name='نوع المستند')
    # بيانات مصلحة الضرائب
    eta_uuid = models.CharField(max_length=36, blank=True, null=True, unique=True,
                                verbose_name='ETA UUID', db_index=True)
    eta_submission_uuid = models.CharField(max_length=36, blank=True, null=True,
                                           verbose_name='Submission UUID')
    eta_long_id = models.CharField(max_length=64, blank=True, null=True,
                                   verbose_name='الرقم الطويل للتحقق')
    eta_internal_id = models.CharField(max_length=64, blank=True, null=True,
                                       verbose_name='Internal ID')
    eta_qr_code = models.TextField(blank=True, null=True, verbose_name='QR Code')
    eta_pdf_url = models.CharField(max_length=500, blank=True, null=True, verbose_name='رابط PDF')

    status = models.CharField(max_length=20, choices=SUBMISSION_STATUS_CHOICES,
                              default='pending', verbose_name='الحالة', db_index=True)
    # تفاصيل المبالغ
    total_sale_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                            verbose_name='إجمالي المبيعات')
    total_discount_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                                verbose_name='إجمالي الخصم')
    net_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                     verbose_name='الصافي')
    total_vat_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                           verbose_name='إجمالي ضريبة القيمة المضافة')
    total_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0,
                                       verbose_name='الإجمالي شامل الضريبة')

    error_message = models.TextField(blank=True, null=True, verbose_name='رسالة الخطأ')
    submission_log = models.TextField(blank=True, null=True, verbose_name='سجل الإرسال')
    submitted_at = models.DateTimeField(blank=True, null=True, verbose_name='تاريخ الإرسال')
    validated_at = models.DateTimeField(blank=True, null=True, verbose_name='تاريخ التحقق')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'فاتورة ضريبية'
        verbose_name_plural = 'الفواتير الضريبية'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tax_invoice_number} - {self.get_status_display()}'

    @property
    def portal_link(self):
        if self.eta_uuid and self.connection:
            return f'{self.connection.portal_url}/public/print/{self.eta_uuid}'
        return None

    def to_eta_document(self):
        """
        تحويل الفاتورة إلى صيغة JSON المطلوبة من منظومة الفاتورة الإلكترونية (ETA)
        حسب مواصفات هيكل المستندات (Document Structure)
        """
        from company.models import Company
        from sales.models import SalesInvoice

        company = Company.get_company()
        invoice = self.sales_invoice

        if not invoice:
            raise ValueError('لا توجد فاتورة مبيعات مرتبطة')

        # بيانات المُصدر (الشركة)
        issuer = {
            'address': {
                'branchID': invoice.branch.code if invoice.branch and invoice.branch.code else '0',
                'country': company.country or 'EG',
                'governate': company.city or '',
                'regionCity': company.city or '',
                'street': company.address or '',
                'buildingNumber': '',
                'postalCode': '',
                'floor': '',
                'room': '',
                'landmark': '',
                'additionalInformation': '',
            },
            'type': 'B' if (company.commercial_register and company.commercial_register.strip()) else 'B',
            'id': (company.tax_number or '').strip(),
            'name': company.name,
        }

        # بيانات المُستقبل (العميل)
        customer = invoice.customer
        receiver = {
            'address': {
                'country': customer.country if hasattr(customer, 'country') and customer.country else 'EG',
                'governate': customer.city or '',
                'regionCity': customer.city or '',
                'street': customer.address or '',
                'buildingNumber': '',
                'postalCode': '',
                'floor': '',
                'room': '',
                'landmark': '',
                'additionalInformation': '',
            },
            'type': 'B' if customer.customer_type == 'company' else 'P',
            'id': (customer.tax_number or '').strip() or '000000000000000',
            'name': customer.name,
        }

        # بنود الفاتورة
        lines = []
        for idx, line in enumerate(invoice.lines.all(), start=1):
            item_total = line.total_price
            discount = (item_total * (line.discount_percent or Decimal('0')) / Decimal('100')).quantize(
                Decimal('0.0000000001'))
            net = item_total - discount
            vat_rate = Decimal('14')
            vat_value = (net * vat_rate / Decimal('100')).quantize(Decimal('0.0000000001'))

            lines.append({
                'description': line.product.name if line.product else 'صنف',
                'itemType': 'GS1',
                'itemCode': line.product.code if line.product and hasattr(line.product, 'code') else f'P{idx}',
                'unitType': 'EA',
                'quantity': float(line.quantity),
                'internalCode': line.product.id.hex if line.product else f'P{idx}',
                'salesTotal': float(item_total),
                'total': float(net + vat_value),
                'valueDifference': 0.0,
                'totalTaxableFees': 0.0,
                'netTotal': float(net),
                'itemsDiscount': float(discount),
                'unitValue': {
                    'currencySold': company.currency_code or 'EGP',
                    'amountEGP': float(line.unit_price),
                    'amountSold': float(line.unit_price),
                    'currencyExchangeRate': 0.0,
                },
                'discount': {
                    'rate': float(line.discount_percent or Decimal('0')),
                    'amount': float(discount),
                },
                'taxableItems': [{
                    'taxType': 'T1',
                    'amount': float(vat_value),
                    'subType': 'V009',
                    'rate': float(vat_rate),
                }],
            })

        document = {
            'issuer': issuer,
            'receiver': receiver,
            'documentType': {'i': 'I', 'c': 'C', 'd': 'D', 's': 'S'}[self.document_type],
            'documentTypeVersion': '1.0',
            'dateTimeIssued': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'taxpayerActivityCode': '4620',  # نشاط المقاولات/الخرسانة — يُعدل حسب الشركة
            'internalID': self.tax_invoice_number,
            'purchaseOrderReference': '',
            'salesOrderReference': '',
            'lines': lines,
            'totalSalesAmount': float(self.total_sale_amount),
            'totalDiscountAmount': float(self.total_discount_amount),
            'netAmount': float(self.net_amount),
            'taxTotals': [{
                'taxType': 'T1',
                'amount': float(self.total_vat_amount),
            }],
            'totalAmount': float(self.total_amount),
            'extraDiscountAmount': 0.0,
            'totalItemsDiscountAmount': float(self.total_discount_amount),
        }
        return document
