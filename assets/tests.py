from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.test import Client, TestCase
from openpyxl import Workbook

from .models import Asset, AssetCategory


class AssetImportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='testuser', password='testpass123')
        self.client = Client()
        self.client.force_login(self.user)

    def _build_xlsx(self, rows):
        wb = Workbook()
        ws = wb.active
        ws.append(['كود الأصل', 'اسم الأصل', 'التصنيف', 'سعر الشراء', 'الإهلاك المتراكم', 'الحالة'])
        for r in rows:
            ws.append(r)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def _upload(self, buf):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return self.client.post(
            '/assets/import/assets/',
            {
                'excel_file': SimpleUploadedFile(
                    'test.xlsx',
                    buf.read(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )
            },
        )

    def test_import_creates_assets_with_decimal_values(self):
        buf = self._build_xlsx(
            [['A1', 'أصل1', 'مباني', '1,234.50', '100.25', 'active'], ['A2', 'أصل2', 'مباني', '500', '', 'active']]
        )
        resp = self._upload(buf)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Asset.objects.count(), 2)
        a1 = Asset.objects.get(code='A1')
        self.assertEqual(a1.purchase_price, Decimal('1234.50'))
        self.assertEqual(a1.accumulated_depreciation, Decimal('100.25'))
        self.assertEqual(a1.net_book_value, Decimal('1134.25'))
        a2 = Asset.objects.get(code='A2')
        self.assertEqual(a2.purchase_price, Decimal('500'))
        self.assertEqual(a2.net_book_value, Decimal('500'))
        self.assertTrue(AssetCategory.objects.filter(name='مباني').exists())

    def test_import_rejects_negative_price_rolls_back(self):
        buf = self._build_xlsx([['A3', 'أصل3', 'مباني', '-500', '0', 'active']])
        resp = self._upload(buf)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Asset.objects.count(), 0)
