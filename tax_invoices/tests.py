import json
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import responses
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from company.models import Company
from purchases.models import Product
from sales.models import Customer, SalesInvoice

from .models import ETAConnection, TaxInvoice
from .services import ETAAPIError, ETAService
from .views import json_dumps_pretty

# ─── Helpers ───────────────────────────────────────────────────────


def _make_response(status_code=200, json_data=None, text=''):
    """إنشاء كائن استجابة وهمي يحاكي requests.Response"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or json.dumps(json_data or {})
    return resp


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db_setup():
    """إنشاء البيانات الأساسية للاختبارات"""
    company = Company.objects.create(
        name='شركة اختبار',
        name_en='Test Co',
        address='القاهرة',
        city='القاهرة',
        country='مصر',
        tax_number='123456789',
        currency='ج.م',
        currency_code='EGP',
        vat_rate=14,
    )
    customer = Customer.objects.create(
        code='C001',
        name='عميل تجريبي',
        customer_type='company',
        tax_number='987654321',
        address='المعادي',
        city='القاهرة',
        country='EG',
    )
    product = Product.objects.create(
        code='P001',
        name='منتج تجريبي',
        purchase_price=Decimal('100.0000000000'),
        selling_price=Decimal('150.0000000000'),
    )
    connection = ETAConnection.objects.create(
        name='إعداد اختبار',
        environment='sandbox',
        client_id='test_client_id',
        client_secret='test_client_secret',
        is_active=True,
    )
    sales_invoice = SalesInvoice.objects.create(
        invoice_number='INV-TEST-001',
        customer=customer,
        date=date.today(),
        payment_method='credit',
        is_tax_invoice=True,
        withholding_tax_type=0,
        subtotal=Decimal('1000.0000000000'),
        vat_amount=Decimal('140.0000000000'),
        discount_amount=Decimal('0.0000000000'),
        withholding_tax_amount=Decimal('0.0000000000'),
        total_amount=Decimal('1140.0000000000'),
        paid_amount=Decimal('0.0000000000'),
        remaining_amount=Decimal('1140.0000000000'),
        cost_of_goods=Decimal('500.0000000000'),
        gross_profit=Decimal('500.0000000000'),
        currency_amount=Decimal('1000.0000000000'),
        exchange_rate=Decimal('1.000000'),
        is_posted=False,
    )
    return {
        'company': company,
        'customer': customer,
        'product': product,
        'connection': connection,
        'sales_invoice': sales_invoice,
    }


@pytest.fixture
def superuser():
    """إنشاء مستخدم مشرف لاختبارات تسجيل الدخول"""
    return User.objects.create_superuser(
        username='testadmin', password='testpass123', email='admin@test.com'
    )


@pytest.fixture
def auth_client(client, superuser):
    """عميل اختبار مسجل الدخول"""
    client.login(username='testadmin', password='testpass123')
    return client


@pytest.fixture
def production_connection():
    """إعداد اتصال بيئة الإنتاج"""
    return ETAConnection.objects.create(
        name='إنتاج',
        environment='production',
        client_id='prod_id',
        client_secret='prod_secret',
        is_active=False,
    )


# ═══════════════════════════════════════════════════════════════════
#  1. اختبارات ETAConnection
# ═══════════════════════════════════════════════════════════════════


class TestETAConnectionModel:
    """اختبارات نموذج اتصال منظومة الفاتورة الإلكترونية"""

    @pytest.mark.django_db
    def test_str_representation(self, db_setup):
        """اختبار تمثيل الكائن كنص"""
        conn = db_setup['connection']
        assert 'إعداد اختبار' in str(conn)
        assert 'Sandbox' in str(conn) or 'sandbox' in str(conn).lower()

    @pytest.mark.django_db
    def test_base_url_sandbox(self, db_setup):
        """اختبار رابط البيئة الاختبارية"""
        conn = db_setup['connection']
        assert conn.base_url == 'https://api.preprod.invoicing.eta.gov.eg/api'

    @pytest.mark.django_db
    def test_base_url_production(self, production_connection):
        """اختبار رابط بيئة الإنتاج"""
        assert production_connection.base_url == 'https://api.invoicing.eta.gov.eg/api'

    @pytest.mark.django_db
    def test_portal_url_sandbox(self, db_setup):
        """اختبار رابط بوابة البيئة الاختبارية"""
        conn = db_setup['connection']
        assert conn.portal_url == 'https://preprod.invoicing.eta.gov.eg'

    @pytest.mark.django_db
    def test_portal_url_production(self, production_connection):
        """اختبار رابط بوابة بيئة الإنتاج"""
        assert production_connection.portal_url == 'https://invoicing.eta.gov.eg'

    @pytest.mark.django_db
    def test_default_values(self):
        """اختبار القيم الافتراضية للنموذج"""
        conn = ETAConnection.objects.create(name='افتراضي')
        assert conn.environment == 'sandbox'
        assert conn.is_active is True
        assert conn.client_id is None
        assert conn.client_secret is None

    @pytest.mark.django_db
    def test_ordering(self):
        """اختبار ترتيب الإعدادات حسب النشاط والوقت"""
        c1 = ETAConnection.objects.create(name='أول', is_active=False)
        c2 = ETAConnection.objects.create(name='ثاني', is_active=True)
        connections = list(ETAConnection.objects.all())
        assert connections[0].pk == c2.pk
        assert connections[1].pk == c1.pk


# ═══════════════════════════════════════════════════════════════════
#  2. اختبارات TaxInvoice Model
# ═══════════════════════════════════════════════════════════════════


class TestTaxInvoiceModel:
    """اختبارات نموذج الفاتورة الضريبية"""

    @pytest.mark.django_db
    def test_create_tax_invoice_all_fields(self, db_setup):
        """اختبار إنشاء فاتورة ضريبية بجميع الحقول"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-001',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            document_type='i',
            status='pending',
            total_sale_amount=Decimal('1000.0000000000'),
            total_discount_amount=Decimal('0.0000000000'),
            net_amount=Decimal('1000.0000000000'),
            total_vat_amount=Decimal('140.0000000000'),
            total_amount=Decimal('1140.0000000000'),
        )
        assert ti.pk is not None
        assert ti.tax_invoice_number == 'TAX-001'
        assert ti.document_type == 'i'
        assert ti.status == 'pending'
        assert ti.total_amount == Decimal('1140.0000000000')

    @pytest.mark.django_db
    def test_str_representation(self, db_setup):
        """اختبار تمثيل الفاتورة الضريبية كنص"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-002',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            status='valid',
        )
        result = str(ti)
        assert 'TAX-002' in result

    @pytest.mark.django_db
    def test_portal_link_with_eta_uuid(self, db_setup):
        """اختبار رابط البوابة عند وجود UUID"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-003',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            eta_uuid='abc-123-def-456',
        )
        link = ti.portal_link
        assert link is not None
        assert 'abc-123-def-456' in link
        assert 'preprod.invoicing.eta.gov.eg' in link

    @pytest.mark.django_db
    def test_portal_link_without_eta_uuid(self, db_setup):
        """اختبار رابط البوابة بدون UUID"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-004',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
        )
        assert ti.portal_link is None

    @pytest.mark.django_db
    def test_unique_tax_invoice_number(self, db_setup):
        """اختبار فريدية رقم الفاتورة الضريبية"""
        TaxInvoice.objects.create(
            tax_invoice_number='TAX-UNIQUE',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
        )
        with pytest.raises(Exception):  # noqa: B017
            TaxInvoice.objects.create(
                tax_invoice_number='TAX-UNIQUE',
                sales_invoice=db_setup['sales_invoice'],
                connection=db_setup['connection'],
            )

    @pytest.mark.django_db
    def test_document_type_choices(self, db_setup):
        """اختبار جميع أنواع المستندات المدعومة"""
        for doc_type, _ in TaxInvoice.DOCUMENT_TYPE_CHOICES:
            ti = TaxInvoice.objects.create(
                tax_invoice_number=f'TAX-{doc_type}-{uuid.uuid4().hex[:6]}',
                sales_invoice=db_setup['sales_invoice'],
                connection=db_setup['connection'],
                document_type=doc_type,
            )
            assert ti.document_type == doc_type

    @pytest.mark.django_db
    def test_submission_status_choices(self, db_setup):
        """اختبار جميع حالات الإرسال"""
        for status_val, _ in TaxInvoice.SUBMISSION_STATUS_CHOICES:
            ti = TaxInvoice.objects.create(
                tax_invoice_number=f'TAX-{status_val}-{uuid.uuid4().hex[:6]}',
                sales_invoice=db_setup['sales_invoice'],
                connection=db_setup['connection'],
                status=status_val,
            )
            assert ti.status == status_val

    @pytest.mark.django_db
    def test_created_by_nullable(self, db_setup):
        """اختبار إمكانية إنشاء الفاتورة بدون مستخدم"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-NOUSER',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
        )
        assert ti.created_by is None

    @pytest.mark.django_db
    def test_sales_invoice_nullable(self, db_setup):
        """اختبار إمكانية إنشاء فاتورة ضريبية بدون فاتورة مبيعات"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-NOSALES',
            connection=db_setup['connection'],
        )
        assert ti.sales_invoice is None

    @pytest.mark.django_db
    def test_eta_fields_blankable(self, db_setup):
        """اختبار أن حقول_eta فارغة افتراضياً"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-BLANKS',
            connection=db_setup['connection'],
        )
        assert ti.eta_uuid is None
        assert ti.eta_submission_uuid is None
        assert ti.eta_long_id is None
        assert ti.eta_qr_code is None


# ═══════════════════════════════════════════════════════════════════
#  3. اختبارات TaxInvoice.to_eta_document()
# ═══════════════════════════════════════════════════════════════════


class TestTaxInvoiceToETADocument:
    """اختبارات تحويل الفاتورة إلى صيغة ETA"""

    @pytest.mark.django_db
    def test_to_eta_document_structure(self, db_setup):
        """اختبار هيكل المستند المُنشأ"""
        from sales.models import SalesInvoiceLine

        SalesInvoiceLine.objects.create(
            invoice=db_setup['sales_invoice'],
            product=db_setup['product'],
            quantity=Decimal('10.0000000000'),
            unit_price=Decimal('100.0000000000'),
            discount_percent=Decimal('0'),
        )
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-ETA-001',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            document_type='i',
            total_sale_amount=Decimal('1000.0000000000'),
            total_discount_amount=Decimal('0.0000000000'),
            net_amount=Decimal('1000.0000000000'),
            total_vat_amount=Decimal('140.0000000000'),
            total_amount=Decimal('1140.0000000000'),
        )
        doc = ti.to_eta_document()
        assert 'issuer' in doc
        assert 'receiver' in doc
        assert 'lines' in doc
        assert doc['documentType'] == 'I'
        assert doc['documentTypeVersion'] == '1.0'
        assert doc['internalID'] == 'TAX-ETA-001'
        assert doc['totalSalesAmount'] == 1000.0
        assert doc['netAmount'] == 1000.0
        assert doc['totalAmount'] == 1140.0

    @pytest.mark.django_db
    def test_to_eta_document_issuer(self, db_setup):
        """اختبار بيانات المُصدر (الشركة) في المستند"""
        from sales.models import SalesInvoiceLine

        SalesInvoiceLine.objects.create(
            invoice=db_setup['sales_invoice'],
            product=db_setup['product'],
            quantity=Decimal('5.0000000000'),
            unit_price=Decimal('200.0000000000'),
            discount_percent=Decimal('0'),
        )
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-ISSUER',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
        )
        doc = ti.to_eta_document()
        issuer = doc['issuer']
        assert issuer['id'] == '123456789'
        assert issuer['name'] == 'شركة اختبار'
        assert issuer['type'] == 'B'

    @pytest.mark.django_db
    def test_to_eta_document_receiver_company(self, db_setup):
        """اختبار بيانات المستقبل عندما يكون العميل شركة"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-RCV',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
        )
        doc = ti.to_eta_document()
        receiver = doc['receiver']
        assert receiver['type'] == 'B'
        assert receiver['id'] == '987654321'
        assert receiver['name'] == 'عميل تجريبي'

    @pytest.mark.django_db
    def test_to_eta_document_receiver_individual(self, db_setup):
        """اختبار بيانات المستقبل عندما يكون العميل فرداً"""
        customer_ind = Customer.objects.create(
            code='C002',
            name='عميل فردي',
            customer_type='individual',
            tax_number='',
            city='الجيزة',
        )
        inv = SalesInvoice.objects.create(
            invoice_number='INV-IND-001',
            customer=customer_ind,
            date=date.today(),
            payment_method='cash',
            subtotal=Decimal('500.0000000000'),
            total_amount=Decimal('570.0000000000'),
        )
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-RCV-IND',
            sales_invoice=inv,
            connection=db_setup['connection'],
        )
        doc = ti.to_eta_document()
        assert doc['receiver']['type'] == 'P'
        assert doc['receiver']['id'] == '000000000000000'

    @pytest.mark.django_db
    def test_to_eta_document_document_type_mapping(self, db_setup):
        """اختبار تطوير أنواع المستندات (i->I, c->C, d->D, s->S)"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-TYPE',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            document_type='c',
        )
        doc = ti.to_eta_document()
        assert doc['documentType'] == 'C'

    @pytest.mark.django_db
    def test_to_eta_document_without_sales_invoice(self, db_setup):
        """اختبار خطأ عند عدم وجود فاتورة مبيعات مرتبطة"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-NOINV',
            connection=db_setup['connection'],
        )
        with pytest.raises(ValueError, match='لا توجد فاتورة مبيعات مرتبطة'):
            ti.to_eta_document()

    @pytest.mark.django_db
    def test_to_eta_document_lines_with_discount(self, db_setup):
        """اختبار بنود الفاتورة مع خصم"""
        from sales.models import SalesInvoiceLine

        SalesInvoiceLine.objects.create(
            invoice=db_setup['sales_invoice'],
            product=db_setup['product'],
            quantity=Decimal('10.0000000000'),
            unit_price=Decimal('100.0000000000'),
            discount_percent=Decimal('10.00'),
        )
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-DISC',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            total_sale_amount=Decimal('1000.0000000000'),
            total_discount_amount=Decimal('100.0000000000'),
            net_amount=Decimal('900.0000000000'),
            total_vat_amount=Decimal('126.0000000000'),
            total_amount=Decimal('1026.0000000000'),
        )
        doc = ti.to_eta_document()
        assert len(doc['lines']) == 1
        line = doc['lines'][0]
        assert line['discount']['rate'] == 10.0
        assert line['taxableItems'][0]['taxType'] == 'T1'
        assert line['taxableItems'][0]['rate'] == 14.0


# ═══════════════════════════════════════════════════════════════════
#  4. اختبارات json_dumps_pretty
# ═══════════════════════════════════════════════════════════════════


class TestJsonDumpsPretty:
    """اختبارات دالة التنسيق JSON"""

    def test_normal_dict(self):
        """اختبار تحويل قاموس عادي إلى JSON منسّق"""
        result = json_dumps_pretty({'key': 'value', 'num': 42})
        parsed = json.loads(result)
        assert parsed['key'] == 'value'
        assert parsed['num'] == 42

    def test_non_ascii_arabic(self):
        """اختبار دعم النصوص العربية (بدون تحويل إلى unicode)"""
        result = json_dumps_pretty({'name': 'شركة تجريبية'})
        assert 'شركة تجريبية' in result

    def test_unserializable_object(self):
        """اختبار معالجة كائن غير قابل للتحويل"""
        result = json_dumps_pretty(set([1, 2, 3]))
        assert isinstance(result, str)

    def test_nested_structure(self):
        """اختبار هيكل متداخل"""
        data = {'a': [1, 2], 'b': {'c': True}}
        result = json_dumps_pretty(data)
        parsed = json.loads(result)
        assert parsed['a'] == [1, 2]
        assert parsed['b']['c'] is True


# ═══════════════════════════════════════════════════════════════════
#  5. اختبارات ETAService
# ═══════════════════════════════════════════════════════════════════


class TestETAServiceAuthenticate:
    """اختبارات خدمة المصادقة مع مصلحة الضرائب"""

    @responses.activate
    @pytest.mark.django_db
    def test_authenticate_success(self, db_setup):
        """اختبار نجاح المصادقة والحصول على توكن"""
        conn = db_setup['connection']
        service = ETAService(conn)
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            json={'access_token': 'test_token_abc123', 'expires_in': 3600},
            status=200,
        )
        token = service.authenticate()
        assert token == 'test_token_abc123'  # noqa: S105
        assert service.token == 'test_token_abc123'  # noqa: S105

    @responses.activate
    @pytest.mark.django_db
    def test_authenticate_failure_wrong_status(self, db_setup):
        """اختبار فشل المصادقة بخطأ في الحالة"""
        conn = db_setup['connection']
        service = ETAService(conn)
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            body='Unauthorized',
            status=401,
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.authenticate()
        assert exc_info.value.status_code == 401
        assert '401' in exc_info.value.message

    @responses.activate
    @pytest.mark.django_db
    def test_authenticate_network_error(self, db_setup):
        """اختبار خطأ في الاتصال بالشبكة"""
        import requests

        conn = db_setup['connection']
        service = ETAService(conn)
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            body=requests.ConnectionError('Network unreachable'),
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.authenticate()
        assert 'فشل الاتصال' in exc_info.value.message

    @responses.activate
    @pytest.mark.django_db
    def test_authenticate_uses_id_token_fallback(self, db_setup):
        """اختبار استخدام id_token كبديل لـ access_token"""
        conn = db_setup['connection']
        service = ETAService(conn)
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            json={'id_token': 'fallback_token_xyz', 'expires_in': 3600},
            status=200,
        )
        token = service.authenticate()
        assert token == 'fallback_token_xyz'  # noqa: S105

    @responses.activate
    @pytest.mark.django_db
    def test_authenticate_caches_token(self, db_setup):
        """اختبار تخزين التوكن مؤقتاً"""
        conn = db_setup['connection']
        service = ETAService(conn)
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            json={'access_token': 'cached_token', 'expires_in': 7200},
            status=200,
        )
        token1 = service.authenticate()
        token2 = service.authenticate()
        assert token1 == token2 == 'cached_token'


class TestETAServiceSubmitDocuments:
    """اختبارات إرسال المستندات لمصلحة الضرائب"""

    def _register_auth(self, conn):
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            json={'access_token': 't', 'expires_in': 3600},
            status=200,
        )

    @responses.activate
    @pytest.mark.django_db
    def test_submit_success_200(self, db_setup):
        """اختبار نجاح الإرسال بكود 200"""
        conn = db_setup['connection']
        service = ETAService(conn)
        doc = {'documentType': 'I', 'internalID': 'T-001'}
        self._register_auth(conn)
        responses.post(
            f'{conn.base_url}/v1/document-submissions',
            json=[{'uuid': 'u1', 'submissionUuid': 's1'}],
            status=200,
        )
        result = service.submit_documents(doc)
        assert isinstance(result, list)
        assert result[0]['uuid'] == 'u1'

    @responses.activate
    @pytest.mark.django_db
    def test_submit_success_202(self, db_setup):
        """اختبار نجاح الإرسال بكود 202"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.post(
            f'{conn.base_url}/v1/document-submissions',
            json={'status': 'accepted'},
            status=202,
        )
        result = service.submit_documents({'doc': 1})
        assert result['status'] == 'accepted'

    @responses.activate
    @pytest.mark.django_db
    def test_submit_success_207(self, db_setup):
        """اختبار نجاح الإرسال بكود 207 (جزئي)"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.post(
            f'{conn.base_url}/v1/document-submissions',
            json=[{'uuid': 'u1', 'status': 'partial'}],
            status=207,
        )
        result = service.submit_documents([{'doc': 1}])
        assert result[0]['status'] == 'partial'

    @responses.activate
    @pytest.mark.django_db
    def test_submit_failure_400(self, db_setup):
        """اختبار فشل الإرسال بكود 400"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.post(
            f'{conn.base_url}/v1/document-submissions',
            body='Bad Request',
            status=400,
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.submit_documents({'doc': 1})
        assert exc_info.value.status_code == 400

    @responses.activate
    @pytest.mark.django_db
    def test_submit_network_error(self, db_setup):
        """اختبار خطأ في الشبكة أثناء الإرسال"""
        import requests

        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.post(
            f'{conn.base_url}/v1/document-submissions',
            body=requests.Timeout('Timed out'),
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.submit_documents({'doc': 1})
        assert 'فشل إرسال' in exc_info.value.message

    @responses.activate
    @pytest.mark.django_db
    def test_submit_wraps_single_dict(self, db_setup):
        """اختبار تحويل المستند المفرد إلى قائمة"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.post(
            f'{conn.base_url}/v1/document-submissions',
            json=[{'uuid': 'u1'}],
            status=200,
        )
        result = service.submit_documents({'doc': 'single'})
        assert isinstance(result, list)


class TestETAServiceGetDocumentStatus:
    """اختبارات متابعة حالة المستند"""

    def _register_auth(self, conn):
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            json={'access_token': 't', 'expires_in': 3600},
            status=200,
        )

    @responses.activate
    @pytest.mark.django_db
    def test_get_status_success(self, db_setup):
        """اختبار نجاح جلب الحالة"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.get(
            f'{conn.base_url}/v1/document-submissions/sub-uuid-123/status',
            json={'is_valid': True, 'status': 'valid'},
            status=200,
        )
        result = service.get_document_status('sub-uuid-123')
        assert result['is_valid'] is True

    @responses.activate
    @pytest.mark.django_db
    def test_get_status_failure(self, db_setup):
        """اختبار فشل جلب الحالة"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.get(
            f'{conn.base_url}/v1/document-submissions/sub-uuid-123/status',
            body='Not Found',
            status=404,
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.get_document_status('sub-uuid-123')
        assert exc_info.value.status_code == 404

    @responses.activate
    @pytest.mark.django_db
    def test_get_status_network_error(self, db_setup):
        """اختبار خطأ في الشبكة أثناء جلب الحالة"""
        import requests

        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.get(
            f'{conn.base_url}/v1/document-submissions/sub-uuid/status',
            body=requests.ConnectionError('Down'),
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.get_document_status('sub-uuid')
        assert 'فشل متابعة' in exc_info.value.message


class TestETAServiceGetDocumentDetails:
    """اختبارات جلب تفاصيل المستند"""

    def _register_auth(self, conn):
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            json={'access_token': 't', 'expires_in': 3600},
            status=200,
        )

    @responses.activate
    @pytest.mark.django_db
    def test_get_details_success(self, db_setup):
        """اختبار نجاح جلب التفاصيل"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        detail_data = {
            'longId': 'LONG123',
            'internalId': 'INT456',
            'qrCode': 'QR_DATA',
            'pdfUrl': 'https://example.com/invoice.pdf',
        }
        responses.get(
            f'{conn.base_url}/v1/documents/doc-uuid-xyz/raw',
            json=detail_data,
            status=200,
        )
        result = service.get_document_details('doc-uuid-xyz')
        assert result['longId'] == 'LONG123'
        assert result['qrCode'] == 'QR_DATA'

    @responses.activate
    @pytest.mark.django_db
    def test_get_details_failure(self, db_setup):
        """اختبار فشل جلب التفاصيل"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.get(
            f'{conn.base_url}/v1/documents/doc-uuid/raw',
            body='Not Found',
            status=404,
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.get_document_details('doc-uuid')
        assert exc_info.value.status_code == 404


class TestETAServiceVoidDocument:
    """اختبارات إلغاء المستند الضريبي"""

    def _register_auth(self, conn):
        responses.post(
            f'{conn.base_url}/v1/auth/token',
            json={'access_token': 't', 'expires_in': 3600},
            status=200,
        )

    @responses.activate
    @pytest.mark.django_db
    def test_void_success_200(self, db_setup):
        """اختبار نجاح الإلغاء بكود 200"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.put(
            f'{conn.base_url}/v1/documents/doc-uuid/state',
            json={'status': 'rejected'},
            status=200,
        )
        result = service.void_document('doc-uuid', reason='خطأ')
        assert result['status'] == 'rejected'

    @responses.activate
    @pytest.mark.django_db
    def test_void_success_204_no_body(self, db_setup):
        """اختبار نجاح الإلغاء بكود 204 بدون محتوى"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.put(
            f'{conn.base_url}/v1/documents/doc-uuid/state',
            body='',
            status=204,
        )
        result = service.void_document('doc-uuid')
        assert result['status'] == 'rejected'

    @responses.activate
    @pytest.mark.django_db
    def test_void_failure(self, db_setup):
        """اختبار فشل الإلغاء"""
        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.put(
            f'{conn.base_url}/v1/documents/doc-uuid/state',
            body='Forbidden',
            status=403,
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.void_document('doc-uuid')
        assert exc_info.value.status_code == 403

    @responses.activate
    @pytest.mark.django_db
    def test_void_network_error(self, db_setup):
        """اختبار خطأ في الشبكة أثناء الإلغاء"""
        import requests

        conn = db_setup['connection']
        service = ETAService(conn)
        self._register_auth(conn)
        responses.put(
            f'{conn.base_url}/v1/documents/doc-uuid/state',
            body=requests.ConnectionError('Down'),
        )
        with pytest.raises(ETAAPIError) as exc_info:
            service.void_document('doc-uuid')
        assert 'فشل إلغاء' in exc_info.value.message


# ═══════════════════════════════════════════════════════════════════
#  6. اختبارات ETAAPIError
# ═══════════════════════════════════════════════════════════════════


class TestETAAPIError:
    """اختبارات كائن الخطأ الخاص بـ API"""

    def test_error_attributes(self):
        """اختبار خصائص الخطأ"""
        err = ETAAPIError('حدث خطأ', status_code=500, response_body='{"error":"fail"}')
        assert err.message == 'حدث خطأ'
        assert err.status_code == 500
        assert err.response_body == '{"error":"fail"}'
        assert str(err) == 'حدث خطأ'

    def test_error_default_values(self):
        """اختبار القيم الافتراضية للخطأ"""
        err = ETAAPIError('فقط رسالة')
        assert err.status_code is None
        assert err.response_body is None


# ═══════════════════════════════════════════════════════════════════
#  7. اختبارات Views
# ═══════════════════════════════════════════════════════════════════


class TestTaxDashboardView:
    """اختبارات لوحة الفواتير الضريبية"""

    @pytest.mark.django_db
    def test_requires_login(self, client):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:dashboard')
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_dashboard_renders(self, auth_client):
        """اختبار عرض لوحة التحكم للمستخدم المسجل"""
        url = reverse('tax_invoices:dashboard')
        response = auth_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_dashboard_context(self, auth_client, db_setup):
        """اختبار بيانات السياق في لوحة التحكم"""
        TaxInvoice.objects.create(
            tax_invoice_number='TAX-DASH',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            status='pending',
        )
        url = reverse('tax_invoices:dashboard')
        response = auth_client.get(url)
        assert response.context['total'] == 1
        assert response.context['pending_count'] == 1


class TestConnectionListView:
    """اختبارات قائمة إعدادات الاتصال"""

    @pytest.mark.django_db
    def test_requires_login(self, client):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:connection_list')
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_list_shows_connections(self, auth_client, db_setup):
        """اختبار عرض الإعدادات"""
        url = reverse('tax_invoices:connection_list')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert db_setup['connection'] in response.context['connections']


class TestConnectionCreateView:
    """اختبارات إنشاء إعداد اتصال جديد"""

    @pytest.mark.django_db
    def test_requires_login(self, client):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:connection_create')
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_get_renders_form(self, auth_client):
        """اختبار عرض نموذج الإنشاء"""
        url = reverse('tax_invoices:connection_create')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert 'environments' in response.context

    @pytest.mark.django_db
    def test_post_creates_connection(self, auth_client):
        """اختبار إنشاء إعداد اتصال عبر POST"""
        url = reverse('tax_invoices:connection_create')
        data = {
            'name': 'إعداد جديد',
            'environment': 'sandbox',
            'client_id': 'new_id',
            'client_secret': 'new_secret',
        }
        response = auth_client.post(url, data)
        assert response.status_code == 302
        assert ETAConnection.objects.filter(name='إعداد جديد').exists()

    @pytest.mark.django_db
    def test_post_active_deactivates_others(self, auth_client, db_setup):
        """اختبار تعطيل الإعدادات الأخرى عند تفعيل جديد"""
        url = reverse('tax_invoices:connection_create')
        data = {
            'name': 'جديد ومفعل',
            'environment': 'sandbox',
            'client_id': 'x',
            'client_secret': 'y',
            'is_active': 'on',
        }
        auth_client.post(url, data)
        db_setup['connection'].refresh_from_db()
        assert db_setup['connection'].is_active is False


class TestConnectionEditView:
    """اختبارات تعديل إعداد الاتصال"""

    @pytest.mark.django_db
    def test_requires_login(self, client, db_setup):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:connection_edit', kwargs={'pk': db_setup['connection'].pk})
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_get_renders_form(self, auth_client, db_setup):
        """اختبار عرض نموذج التعديل"""
        url = reverse('tax_invoices:connection_edit', kwargs={'pk': db_setup['connection'].pk})
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.context['conn'] == db_setup['connection']

    @pytest.mark.django_db
    def test_post_updates_connection(self, auth_client, db_setup):
        """اختبار تحديث الإعداد عبر POST"""
        url = reverse('tax_invoices:connection_edit', kwargs={'pk': db_setup['connection'].pk})
        data = {
            'name': 'تم التعديل',
            'environment': 'production',
            'client_id': 'updated_id',
            'client_secret': 'updated_secret',
        }
        response = auth_client.post(url, data)
        assert response.status_code == 302
        db_setup['connection'].refresh_from_db()
        assert db_setup['connection'].name == 'تم التعديل'
        assert db_setup['connection'].environment == 'production'


class TestTaxInvoiceListView:
    """اختبارات قائمة الفواتير الضريبية"""

    @pytest.mark.django_db
    def test_requires_login(self, client):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:tax_invoice_list')
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_list_renders(self, auth_client):
        """اختبار عرض القائمة"""
        url = reverse('tax_invoices:tax_invoice_list')
        response = auth_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_filter_by_status(self, auth_client, db_setup):
        """اختبار تصفية الفواتير حسب الحالة"""
        TaxInvoice.objects.create(
            tax_invoice_number='TAX-F1',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            status='valid',
        )
        inv2 = SalesInvoice.objects.create(
            invoice_number='INV-002',
            customer=db_setup['customer'],
            date=date.today(),
            payment_method='cash',
            total_amount=Decimal('500.0000000000'),
        )
        TaxInvoice.objects.create(
            tax_invoice_number='TAX-F2',
            sales_invoice=inv2,
            connection=db_setup['connection'],
            status='failed',
        )
        url = reverse('tax_invoices:tax_invoice_list')
        response = auth_client.get(url, {'status': 'valid'})
        assert response.status_code == 200
        assert response.context['current_status'] == 'valid'


class TestTaxInvoiceDetailView:
    """اختبارات تفاصيل الفاتورة الضريبية"""

    @pytest.mark.django_db
    def test_requires_login(self, client):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:tax_invoice_detail', kwargs={'pk': uuid.uuid4()})
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_detail_renders(self, auth_client, db_setup):
        """اختبار عرض التفاصيل"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-DET',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
        )
        url = reverse('tax_invoices:tax_invoice_detail', kwargs={'pk': ti.pk})
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.context['tax_invoice'] == ti

    @pytest.mark.django_db
    def test_detail_404(self, auth_client):
        """اختبار عدم العثور على الفاتورة"""
        url = reverse('tax_invoices:tax_invoice_detail', kwargs={'pk': uuid.uuid4()})
        response = auth_client.get(url)
        assert response.status_code == 404


class TestTaxInvoiceCreateFromSalesView:
    """اختبارات إنشاء فاتورة ضريبية من فاتورة مبيعات"""

    @pytest.mark.django_db
    def test_requires_login(self, client):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:tax_invoice_create_from_sales', kwargs={'sales_pk': uuid.uuid4()})
        response = client.post(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_requires_post(self, auth_client, db_setup):
        """اختبار رفض طلب GET"""
        url = reverse(
            'tax_invoices:tax_invoice_create_from_sales',
            kwargs={'sales_pk': db_setup['sales_invoice'].pk},
        )
        response = auth_client.get(url)
        assert response.status_code == 405

    @pytest.mark.django_db
    def test_no_active_connection_redirects(self, auth_client, db_setup):
        """اختبار التوجيه عند عدم وجود اتصال مفعل"""
        db_setup['connection'].is_active = False
        db_setup['connection'].save()
        url = reverse(
            'tax_invoices:tax_invoice_create_from_sales',
            kwargs={'sales_pk': db_setup['sales_invoice'].pk},
        )
        response = auth_client.post(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_duplicate_tax_invoice_warns(self, auth_client, db_setup):
        """اختبار تحذير عند إرسال فاتورة مرسلة مسبقاً"""
        TaxInvoice.objects.create(
            tax_invoice_number='TAX-DUP',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
        )
        url = reverse(
            'tax_invoices:tax_invoice_create_from_sales',
            kwargs={'sales_pk': db_setup['sales_invoice'].pk},
        )
        response = auth_client.post(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_creates_and_submits_successfully(self, auth_client, db_setup):
        """اختبار إنشاء وإرسال الفاتورة بنجاح"""
        url = reverse(
            'tax_invoices:tax_invoice_create_from_sales',
            kwargs={'sales_pk': db_setup['sales_invoice'].pk},
        )
        submit_response = [{'uuid': 'eta-u1', 'submissionUuid': 'eta-s1'}]
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.submit_documents.return_value = submit_response
            response = auth_client.post(url)
            assert response.status_code == 302
            ti = TaxInvoice.objects.get(tax_invoice_number=db_setup['sales_invoice'].invoice_number)
            assert ti.status == 'submitted'
            assert ti.eta_uuid == 'eta-u1'
            assert ti.eta_submission_uuid == 'eta-s1'

    @pytest.mark.django_db
    def test_handles_eta_api_error(self, auth_client, db_setup):
        """اختبار معالجة خطأ من API الضرائب"""
        url = reverse(
            'tax_invoices:tax_invoice_create_from_sales',
            kwargs={'sales_pk': db_setup['sales_invoice'].pk},
        )
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.submit_documents.side_effect = ETAAPIError(
                'فشل المصادقة', status_code=401
            )
            response = auth_client.post(url)
            assert response.status_code == 302
            ti = TaxInvoice.objects.get(tax_invoice_number=db_setup['sales_invoice'].invoice_number)
            assert ti.status == 'failed'
            assert 'فشل المصادقة' in ti.error_message

    @pytest.mark.django_db
    def test_handles_unexpected_error(self, auth_client, db_setup):
        """اختبار معالجة خطأ غير متوقع"""
        url = reverse(
            'tax_invoices:tax_invoice_create_from_sales',
            kwargs={'sales_pk': db_setup['sales_invoice'].pk},
        )
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.submit_documents.side_effect = RuntimeError('خطأ برمجي')
            response = auth_client.post(url)
            assert response.status_code == 302
            ti = TaxInvoice.objects.get(tax_invoice_number=db_setup['sales_invoice'].invoice_number)
            assert ti.status == 'failed'

    @pytest.mark.django_db
    def test_handles_dict_response(self, auth_client, db_setup):
        """اختبار معالجة استجابة على شكل قاموس"""
        url = reverse(
            'tax_invoices:tax_invoice_create_from_sales',
            kwargs={'sales_pk': db_setup['sales_invoice'].pk},
        )
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.submit_documents.return_value = {
                'uuid': 'dict-u1',
                'submissionUuid': 'dict-s1',
            }
            response = auth_client.post(url)
            assert response.status_code == 302
            ti = TaxInvoice.objects.get(tax_invoice_number=db_setup['sales_invoice'].invoice_number)
            assert ti.status == 'submitted'
            assert ti.eta_uuid == 'dict-u1'

    @pytest.mark.django_db
    def test_handles_unexpected_response_format(self, auth_client, db_setup):
        """اختبار معالجة استجابة بصيغة غير متوقعة"""
        url = reverse(
            'tax_invoices:tax_invoice_create_from_sales',
            kwargs={'sales_pk': db_setup['sales_invoice'].pk},
        )
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.submit_documents.return_value = None
            response = auth_client.post(url)
            assert response.status_code == 302
            ti = TaxInvoice.objects.get(tax_invoice_number=db_setup['sales_invoice'].invoice_number)
            assert ti.status == 'failed'


class TestTaxInvoiceCheckStatusView:
    """اختبارات متابعة حالة الفاتورة الضريبية"""

    @pytest.mark.django_db
    def test_requires_login(self, client):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:tax_invoice_check_status', kwargs={'pk': uuid.uuid4()})
        response = client.post(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_no_submission_uuid_redirects(self, auth_client, db_setup):
        """اختبار التوجيه عند عدم وجود رقم متابعة"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-NOSUB',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
        )
        url = reverse('tax_invoices:tax_invoice_check_status', kwargs={'pk': ti.pk})
        response = auth_client.post(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_check_status_valid(self, auth_client, db_setup):
        """اختبار تأكيد الحالة الصالحة"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-CHK',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            eta_uuid='chk-uuid-123',
            eta_submission_uuid='chk-sub-123',
            status='submitted',
        )
        url = reverse('tax_invoices:tax_invoice_check_status', kwargs={'pk': ti.pk})
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_document_status.return_value = {
                'is_valid': True,
                'status': 'valid',
            }
            mock_instance.get_document_details.return_value = {
                'longId': 'LONG999',
                'qrCode': 'QR_DATA',
            }
            response = auth_client.post(url)
            assert response.status_code == 302
            ti.refresh_from_db()
            assert ti.status == 'valid'
            assert ti.eta_long_id == 'LONG999'
            assert ti.eta_qr_code == 'QR_DATA'

    @pytest.mark.django_db
    def test_check_status_invalid(self, auth_client, db_setup):
        """اختبار حالة فاتورة غير صالحة"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-INV',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            eta_submission_uuid='inv-sub-123',
            status='submitted',
        )
        url = reverse('tax_invoices:tax_invoice_check_status', kwargs={'pk': ti.pk})
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_document_status.return_value = {
                'is_valid': False,
                'status': 'invalid',
            }
            response = auth_client.post(url)
            ti.refresh_from_db()
            assert ti.status == 'invalid'

    @pytest.mark.django_db
    def test_check_status_eta_error(self, auth_client, db_setup):
        """اختبار معالجة خطأ من API أثناء متابعة الحالة"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-ERR',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            eta_submission_uuid='err-sub-123',
            status='submitted',
        )
        url = reverse('tax_invoices:tax_invoice_check_status', kwargs={'pk': ti.pk})
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_document_status.side_effect = ETAAPIError(
                'Timeout', status_code=504
            )
            response = auth_client.post(url)
            assert response.status_code == 302


class TestTaxInvoiceVoidView:
    """اختبارات إلغاء الفاتورة الضريبية"""

    @pytest.mark.django_db
    def test_requires_login(self, client):
        """اختبار طلب تسجيل الدخول"""
        url = reverse('tax_invoices:tax_invoice_void', kwargs={'pk': uuid.uuid4()})
        response = client.post(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_already_cancelled(self, auth_client, db_setup):
        """اختبار رفض الإلغاء المكرر"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-CANC',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            status='cancelled',
        )
        url = reverse('tax_invoices:tax_invoice_void', kwargs={'pk': ti.pk})
        response = auth_client.post(url)
        assert response.status_code == 302
        ti.refresh_from_db()
        assert ti.status == 'cancelled'

    @pytest.mark.django_db
    def test_void_success(self, auth_client, db_setup):
        """اختبار نجاح الإلغاء"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-VoidOK',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            eta_uuid='void-uuid-123',
            status='valid',
        )
        url = reverse('tax_invoices:tax_invoice_void', kwargs={'pk': ti.pk})
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.void_document.return_value = {'status': 'rejected'}
            response = auth_client.post(url)
            assert response.status_code == 302
            ti.refresh_from_db()
            assert ti.status == 'cancelled'

    @pytest.mark.django_db
    def test_void_eta_error(self, auth_client, db_setup):
        """اختبار معالجة خطأ من API أثناء الإلغاء"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-VoidErr',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            eta_uuid='void-err-uuid',
            status='valid',
        )
        url = reverse('tax_invoices:tax_invoice_void', kwargs={'pk': ti.pk})
        with patch('tax_invoices.views.ETAService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.void_document.side_effect = ETAAPIError(
                'Access Denied', status_code=403
            )
            response = auth_client.post(url)
            assert response.status_code == 302
            ti.refresh_from_db()
            assert ti.status != 'cancelled'

    @pytest.mark.django_db
    def test_void_without_eta_uuid(self, auth_client, db_setup):
        """اختبار الإلغاء بدون UUID (محلي فقط)"""
        ti = TaxInvoice.objects.create(
            tax_invoice_number='TAX-VoidLocal',
            sales_invoice=db_setup['sales_invoice'],
            connection=db_setup['connection'],
            status='failed',
        )
        url = reverse('tax_invoices:tax_invoice_void', kwargs={'pk': ti.pk})
        response = auth_client.post(url)
        assert response.status_code == 302
        ti.refresh_from_db()
        assert ti.status == 'cancelled'


# ═══════════════════════════════════════════════════════════════════
#  8. اختبارات Admin
# ═══════════════════════════════════════════════════════════════════


class TestAdminRegistration:
    """اختبارات تسجيل النماذج في لوحة التحكم"""

    def test_eta_connection_registered(self):
        """اختبار تسجيل ETAConnection في Admin"""
        from django.contrib.admin.sites import AdminSite

        from .admin import ETAConnectionAdmin

        site = AdminSite()
        admin_obj = ETAConnectionAdmin(ETAConnection, site)
        assert 'name' in admin_obj.list_display
        assert 'environment' in admin_obj.list_display

    def test_tax_invoice_registered(self):
        """اختبار تسجيل TaxInvoice في Admin"""
        from django.contrib.admin.sites import AdminSite

        from .admin import TaxInvoiceAdmin

        site = AdminSite()
        admin_obj = TaxInvoiceAdmin(TaxInvoice, site)
        assert 'tax_invoice_number' in admin_obj.list_display
        assert 'status' in admin_obj.list_display
        assert 'eta_uuid' in admin_obj.readonly_fields
