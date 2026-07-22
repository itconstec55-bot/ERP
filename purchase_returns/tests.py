from decimal import Decimal

from django.test import TestCase

from purchases.models import Product, Supplier

from .models import PurchaseReturn, PurchaseReturnLine


class PurchaseReturnTotalsTest(TestCase):
    def test_calculate_totals_uses_decimal_vat(self):
        supplier = Supplier.objects.create(code='S1', name='مورد')
        product = Product.objects.create(
            code='P1', name='منتج', purchase_price=Decimal('10'), selling_price=Decimal('15')
        )
        pr = PurchaseReturn.objects.create(return_number='PR-1', date='2026-01-01', supplier=supplier)
        PurchaseReturnLine.objects.create(purchase_return=pr, product=product, quantity=3, unit_price=Decimal('50'))
        pr.calculate_totals()
        self.assertEqual(pr.subtotal, Decimal('150'))
        self.assertEqual(pr.vat_amount, Decimal('21'))
        self.assertEqual(pr.total_amount, Decimal('171'))
