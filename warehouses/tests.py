from datetime import date, timedelta
from decimal import Decimal

import pytest

from purchases.models import Product, ProductCategory, UnitOfMeasure
from warehouses.models import StockMovement, Warehouse, WarehouseProduct


def _make_product():
    uom, _ = UnitOfMeasure.objects.get_or_create(code='EA', defaults={'name': 'قطعة'})
    cat, _ = ProductCategory.objects.get_or_create(code='CAT', defaults={'name': 'فئة'})
    return Product.objects.create(
        code='PROD-1',
        name='منتج اختبار',
        category=cat,
        unit=uom,
        purchase_price=Decimal('10'),
        selling_price=Decimal('15'),
    )


@pytest.mark.django_db
class TestWarehouse:
    def test_create(self):
        w = Warehouse.objects.create(code='WH-1', name='المخزن الرئيسي', location='الدور الأول')
        assert w.pk is not None
        assert w.is_active is True
        assert str(w) == 'WH-1 - المخزن الرئيسي'


@pytest.mark.django_db
class TestWarehouseProduct:
    def test_create(self):
        w = Warehouse.objects.create(code='WH-2', name='مخزن أ')
        p = _make_product()
        wp = WarehouseProduct.objects.create(warehouse=w, product=p, quantity=Decimal('100'))
        assert wp.pk is not None
        assert wp.quantity == Decimal('100')


@pytest.mark.django_db
class TestStockMovement:
    def test_create_out(self):
        w = Warehouse.objects.create(code='WH-3', name='مخزن ب')
        p = _make_product()
        movement = StockMovement.objects.create(
            movement_number='SM-001',
            movement_type='out',
            warehouse=w,
            product=p,
            quantity=Decimal('10'),
            unit_cost=Decimal('50'),
            date=date.today(),
        )
        assert movement.pk is not None
        assert movement.movement_type == 'out'

    def test_str(self):
        w = Warehouse.objects.create(code='WH-4', name='مخزن ج')
        p = _make_product()
        movement = StockMovement.objects.create(
            movement_number='SM-002',
            movement_type='in',
            warehouse=w,
            product=p,
            quantity=Decimal('20'),
            unit_cost=Decimal('30'),
            date=date.today(),
        )
        assert 'SM-002' in str(movement) or 'مخزن' in str(movement)
