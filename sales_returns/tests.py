from decimal import Decimal

from django.test import TestCase

from purchases.models import Product
from sales.models import Customer

from .models import SalesReturn, SalesReturnLine


class SalesReturnTotalsTest(TestCase):
    def test_calculate_totals_uses_decimal_vat(self):
        customer = Customer.objects.create(code='C1', name='عميل')
        product = Product.objects.create(
            code='P1', name='منتج', purchase_price=Decimal('10'), selling_price=Decimal('15')
        )
        sr = SalesReturn.objects.create(return_number='RET-1', date='2026-01-01', customer=customer)
        SalesReturnLine.objects.create(sales_return=sr, product=product, quantity=2, unit_price=Decimal('100'))
        sr.calculate_totals()
        self.assertEqual(sr.subtotal, Decimal('200'))
        self.assertEqual(sr.vat_amount, Decimal('28'))
        self.assertEqual(sr.total_amount, Decimal('228'))
