"""
 اختبارات نماذج العملات وأسعار الصرف
"""

import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from currency.models import Currency, ExchangeRateHistory


class TestCurrencyModel(TestCase):
    """اختبار نموذج العملة"""

    def setUp(self):
        self.usd = Currency.objects.create(
            code='USD',
            name='دولار أمريكي',
            symbol='$',
            exchange_rate_to_egp=Decimal('30.900000'),
            is_base=False,
        )

    def test_create_currency(self):
        """اختبار إنشاء عملة"""
        self.assertEqual(self.usd.code, 'USD')
        self.assertEqual(self.usd.name, 'دولار أمريكي')
        self.assertEqual(self.usd.symbol, '$')
        self.assertTrue(self.usd.is_active)

    def test_str_representation(self):
        """اختبار تمثيل النص للعملة"""
        self.assertEqual(str(self.usd), 'USD - دولار أمريكي')

    def test_uuid_primary_key(self):
        """اختبار أن المعرف الرئيسي UUID"""
        self.assertIsInstance(self.usd.id, uuid.UUID)

    def test_convert_to_egp(self):
        """اختبار تحويل العملة إلى جنيه مصري"""
        result = self.usd.convert_to_egp(Decimal('100'))
        expected = Decimal('100') * Decimal('30.900000')
        self.assertEqual(result, expected)

    def test_convert_from_egp(self):
        """اختبار التحويل من جنيه مصري إلى العملة"""
        result = self.usd.convert_from_egp(Decimal('3090'))
        self.assertEqual(result, Decimal('100'))

    def test_convert_from_egp_zero_rate(self):
        """اختبار التحويل عند سعر صفر"""
        zero_rate = Currency.objects.create(
            code='ZAR',
            name='عملة صفري',
            symbol='Z',
            exchange_rate_to_egp=Decimal('0'),
        )
        result = zero_rate.convert_from_egp(Decimal('100'))
        self.assertEqual(result, 0)

    def test_is_base_currency(self):
        """اختبار العملة الأساسية"""
        egp = Currency.objects.create(
            code='EGP',
            name='جنيه مصري',
            symbol='ج.م',
            exchange_rate_to_egp=Decimal('1.000000'),
            is_base=True,
        )
        self.assertTrue(egp.is_base)

    def test_only_one_base_currency_enforced(self):
        """اختبار فرض وجود عملة أساسية واحدة فقط"""
        egp = Currency.objects.create(
            code='EGP',
            name='جنيه مصري',
            symbol='ج.م',
            is_base=True,
        )
        eur = Currency(
            code='EUR',
            name='يورو',
            symbol='EUR',
            is_base=True,
        )
        with self.assertRaises(ValidationError):
            eur.full_clean()

    def test_active_default_true(self):
        """اختبار أن الحالة الافتراضية نشطة"""
        cur = Currency.objects.create(
            code='GBP',
            name='جنيه إسترليني',
            symbol='GBP',
        )
        self.assertTrue(cur.is_active)

    def test_unique_code(self):
        """اختبار فرادة كود العملة"""
        with self.assertRaises(Exception):  # noqa: B017
            Currency.objects.create(
                code='USD',
                name='مكرر',
                symbol='X',
            )

    def test_exchange_rate_precision(self):
        """اختبار دقة سعر الصرف"""
        cur = Currency.objects.create(
            code='JPY',
            name='ين ياباني',
            symbol='JPY',
            exchange_rate_to_egp=Decimal('0.207600'),
        )
        self.assertEqual(cur.exchange_rate_to_egp, Decimal('0.207600'))


class TestExchangeRateHistoryModel(TestCase):
    """اختبار نموذج سجل سعر الصرف"""

    def setUp(self):
        self.usd = Currency.objects.create(
            code='USD',
            name='دولار أمريكي',
            symbol='$',
            exchange_rate_to_egp=Decimal('30.900000'),
        )
        self.rate_record = ExchangeRateHistory.objects.create(
            currency=self.usd,
            rate=Decimal('30.900000'),
            date='2024-06-15',
            notes='سعر الصرف اليوم',
        )

    def test_create_exchange_rate(self):
        """اختبار إنشاء سجل سعر صرف"""
        self.assertEqual(self.rate_record.rate, Decimal('30.900000'))
        self.assertEqual(str(self.rate_record.date), '2024-06-15')

    def test_str_representation(self):
        """اختبار تمثيل النص لسجل سعر الصرف"""
        self.assertIn('USD', str(self.rate_record))
        self.assertIn('30.900000', str(self.rate_record))

    def test_uuid_primary_key(self):
        """اختبار أن المعرف الرئيسي UUID"""
        self.assertIsInstance(self.rate_record.id, uuid.UUID)

    def test_notes_optional(self):
        """اختبار أن الملاحظات اختيارية"""
        record = ExchangeRateHistory.objects.create(
            currency=self.usd,
            rate=Decimal('31.000000'),
            date='2024-06-16',
        )
        self.assertEqual(record.notes, '')

    def test_ordering_by_date_desc(self):
        """اختبار الترتيب تنازلي حسب التاريخ"""
        ExchangeRateHistory.objects.create(
            currency=self.usd,
            rate=Decimal('31.500000'),
            date='2024-06-10',
        )
        ExchangeRateHistory.objects.create(
            currency=self.usd,
            rate=Decimal('30.800000'),
            date='2024-06-20',
        )
        records = list(ExchangeRateHistory.objects.all())
        self.assertEqual(records[0].date.year, 2024)
        self.assertGreaterEqual(records[0].date, records[1].date)

    def test_multiple_rates_same_currency(self):
        """اختبار عدة أسعار لنفس العملة"""
        ExchangeRateHistory.objects.create(
            currency=self.usd,
            rate=Decimal('31.000000'),
            date='2024-06-01',
        )
        ExchangeRateHistory.objects.create(
            currency=self.usd,
            rate=Decimal('31.500000'),
            date='2024-06-15',
        )
        self.assertEqual(self.usd.rate_history.count(), 3)

    def test_cascade_delete_currency(self):
        """اختبار الحذف المتسلسل عند حذف العملة"""
        cur = Currency.objects.create(
            code='TEMP',
            name='مؤقت',
            symbol='T',
        )
        ExchangeRateHistory.objects.create(
            currency=cur,
            rate=Decimal('1.000000'),
            date='2024-06-01',
        )
        self.assertEqual(ExchangeRateHistory.objects.filter(currency=cur).count(), 1)
        cur.delete()
        self.assertEqual(ExchangeRateHistory.objects.filter(currency=cur).count(), 0)


class TestCurrencyViews(TestCase):
    """اختبار شاشات العملات"""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin_cur', 'cur@test.com', 'admin123')
        self.client = Client()
        self.client.force_login(self.admin)
        self.usd = Currency.objects.create(
            code='USD',
            name='دولار أمريكي',
            symbol='$',
            exchange_rate_to_egp=Decimal('30.900000'),
        )

    def test_currency_list_returns_200(self):
        """اختبار إرجاع 200 لقائمة العملات"""
        resp = self.client.get(reverse('currency:currency_list'))
        self.assertEqual(resp.status_code, 200)

    def test_currency_create_form(self):
        """اختبار نموذج إنشاء عملة"""
        resp = self.client.get(reverse('currency:currency_create'))
        self.assertEqual(resp.status_code, 200)

    def test_currency_edit_returns_200(self):
        """اختبار إرجاع 200 لصفحة تعديل العملة"""
        resp = self.client.get(reverse('currency:currency_edit', args=[self.usd.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_exchange_rate_history_returns_200(self):
        """اختبار إرجاع 200 لسجل أسعار الصرف"""
        resp = self.client.get(reverse('currency:exchange_rate_history'))
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_redirects(self):
        """اختبار إعادة توجيه غير المسجل"""
        anon_client = Client()
        resp = anon_client.get(reverse('currency:currency_list'))
        self.assertEqual(resp.status_code, 302)
