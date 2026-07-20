import pytest
from decimal import Decimal
from warehouses.models import Warehouse, WarehouseProduct, StockMovement


@pytest.mark.django_db
class TestWarehouse:
    def test_create(self):
        w = Warehouse.objects.create(name='المخزن الرئيسي', location='الدور الأول')
        assert w.pk is not None
        assert w.is_active is True
        assert str(w) == 'المخزن الرئيسي'


@pytest.mark.django_db
class TestWarehouseProduct:
    def test_create(self):
        w = Warehouse.objects.create(name='مخزن أ')
        wp = WarehouseProduct.objects.create(
            warehouse=w,
            quantity=Decimal('100'),
        )
        assert wp.pk is not None
        assert wp.quantity == Decimal('100')


@pytest.mark.django_db
class TestStockMovement:
    def test_create_out(self):
        w = Warehouse.objects.create(name='مخزن ب')
        movement = StockMovement.objects.create(
            movement_number='SM-001',
            movement_type='out',
            warehouse=w,
            quantity=Decimal('10'),
            unit_cost=Decimal('50'),
        )
        assert movement.pk is not None
        assert movement.movement_type == 'out'

    def test_str(self):
        w = Warehouse.objects.create(name='مخزن ج')
        movement = StockMovement.objects.create(
            movement_number='SM-002',
            movement_type='in',
            warehouse=w,
            quantity=Decimal('20'),
            unit_cost=Decimal('30'),
        )
        assert 'SM-002' in str(movement) or 'مخزن' in str(movement)
