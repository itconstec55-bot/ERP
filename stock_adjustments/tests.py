from decimal import Decimal
from django.test import TestCase
from warehouses.models import Warehouse, WarehouseProduct
from purchases.models import Product
from .models import StockAdjustment, StockAdjustmentLine


class StockAdjustmentApproveTest(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name='مخزن', code='W1')
        self.product = Product.objects.create(
            code='P1', name='منتج', purchase_price=Decimal('10'), selling_price=Decimal('15'),
        )
        self.wp = WarehouseProduct.objects.create(
            warehouse=self.warehouse, product=self.product, quantity=Decimal('5'),
        )

    def test_deduction_insufficient_stock_raises_and_keeps_draft(self):
        adj = StockAdjustment.objects.create(
            adjustment_number='ADJ-1', date='2026-01-01',
            adjustment_type='deduction', warehouse=self.warehouse,
        )
        StockAdjustmentLine.objects.create(adjustment=adj, product=self.product, quantity=Decimal('10'))
        with self.assertRaises(ValueError):
            adj.approve()
        adj.refresh_from_db()
        self.assertEqual(adj.status, 'draft')
        self.wp.refresh_from_db()
        self.assertEqual(self.wp.quantity, Decimal('5'))

    def test_addition_updates_stock_and_approves(self):
        adj = StockAdjustment.objects.create(
            adjustment_number='ADJ-2', date='2026-01-01',
            adjustment_type='addition', warehouse=self.warehouse,
        )
        StockAdjustmentLine.objects.create(adjustment=adj, product=self.product, quantity=Decimal('3'))
        adj.approve()
        self.wp.refresh_from_db()
        self.assertEqual(self.wp.quantity, Decimal('8'))
        adj.refresh_from_db()
        self.assertEqual(adj.status, 'approved')
