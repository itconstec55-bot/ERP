import json
import logging
from datetime import datetime

from django.conf import settings

from .models import SyncLog

logger = logging.getLogger('accounting')


SYNC_ORDER_MASTER = [
    ('company', 'Company'),
    ('company', 'CompanyBranch'),
    ('accounts', 'AccountType'),
    ('accounts', 'Account'),
    ('hr', 'Department'),
    ('hr', 'Employee'),
    ('sales', 'Customer'),
    ('purchases', 'Supplier'),
    ('purchases', 'ProductCategory'),
    ('purchases', 'Product'),
    ('treasury', 'Bank'),
    ('treasury', 'Safe'),
    ('assets', 'AssetCategory'),
    ('assets', 'Asset'),
    ('warehouses', 'Warehouse'),
    ('warehouses', 'WarehouseProduct'),
    ('documents', 'DocumentType'),
    ('documents', 'DocumentTemplate'),
]

SYNC_ORDER_TRANSACTION = [
    ('accounts', 'JournalEntry'),
    ('accounts', 'JournalEntryLine'),
    ('sales', 'SalesInvoice'),
    ('sales', 'SalesInvoiceLine'),
    ('purchases', 'PurchaseInvoice'),
    ('purchases', 'PurchaseInvoiceLine'),
    ('treasury', 'BankTransaction'),
    ('treasury', 'SafeTransaction'),
    ('assets', 'DepreciationEntry'),
    ('hr', 'Attendance'),
    ('hr', 'Salary'),
    ('warehouses', 'StockMovement'),
    ('documents', 'Document'),
    ('documents', 'DocumentFlow'),
]

ALL_SYNC_MODELS = SYNC_ORDER_MASTER + SYNC_ORDER_TRANSACTION


def _get_model(app_label, model_name):
    from django.apps import apps

    return apps.get_model(app_label, model_name)


def _model_to_dict(instance, fields=None):
    data = {}
    for field in instance._meta.fields:
        if fields and field.name not in fields:
            continue
        value = getattr(instance, field.name)
        if hasattr(field, 'remote_field') and field.remote_field:
            fk_field = field.name + '_id'
            data[field.name] = str(getattr(instance, fk_field)) if getattr(instance, fk_field) else None
        elif field.name == 'id':
            data[field.name] = str(value) if value else None
        elif hasattr(value, 'isoformat'):
            data[field.name] = value.isoformat()
        elif isinstance(value, bytes):
            data[field.name] = None
        elif hasattr(value, 'name') and hasattr(value, 'url'):
            data[field.name] = value.name if value.name else None
        else:
            try:
                json.dumps(value)
                data[field.name] = value
            except (TypeError, ValueError):
                data[field.name] = str(value) if value else None
    return data


def _dict_to_model_data(app_label, model_name, data):
    model = _get_model(app_label, model_name)
    field_names = {f.name for f in model._meta.fields}

    cleaned = {}
    for key, value in data.items():
        if key not in field_names:
            continue
        if key in ('created_at', 'updated_at'):
            continue
        cleaned[key] = value

    return cleaned


def export_data(machine_id=None, limit=None, offset=0):
    export = {
        'sync_manifest': {
            'source_machine': settings.MACHINE_ID,
            'exported_at': datetime.now().isoformat(),
            'record_count': 0,
            'paginated': limit is not None,
            'limit': limit,
            'offset': offset,
        },
        'data': {},
    }

    total = 0
    for app_label, model_name in ALL_SYNC_MODELS:
        try:
            model = _get_model(app_label, model_name)
            key = f'{app_label}.{model_name}'
            qs = model.objects.all()
            if limit is not None:
                qs = qs[offset : offset + limit]
            records = [_model_to_dict(obj) for obj in qs]
            export['data'][key] = records
            total += len(records)
        except Exception as e:
            logger.exception('Sync export error for %s.%s: %s', app_label, model_name, e)
            continue

    export['sync_manifest']['record_count'] = total
    return export


def import_data(data, source_machine_id=None):
    results = {'imported': 0, 'skipped': 0, 'errors': []}

    sync_data = data.get('data', {})

    for app_label, model_name in ALL_SYNC_MODELS:
        key = f'{app_label}.{model_name}'
        if key not in sync_data:
            continue

        records = sync_data[key]
        if not records:
            continue

        try:
            model = _get_model(app_label, model_name)
        except Exception as e:
            logger.exception('Sync import model lookup error %s.%s: %s', app_label, model_name, e)
            continue

        for record_data in records:
            try:
                cleaned = _dict_to_model_data(app_label, model_name, record_data)
                if 'id' in cleaned and cleaned['id']:
                    obj, created = model.objects.update_or_create(id=cleaned['id'], defaults=cleaned)
                else:
                    cleaned.pop('id', None)
                    obj = model.objects.create(**cleaned)
                results['imported'] += 1
            except Exception as e:
                results['errors'].append({'model': key, 'error': str(e), 'record_id': record_data.get('id', 'unknown')})
                results['skipped'] += 1

    return results


def recalculate_balances():
    from django.db.models import Sum

    from accounts.models import Account, JournalEntryLine
    from purchases.models import Product, Supplier
    from sales.models import Customer

    try:
        # الحسابات: تجميع القيود المرحّلة لكل حساب دفعة واحدة (دون N+1)
        lines = (
            JournalEntryLine.objects.filter(journal_entry__is_posted=True, journal_entry__is_reversed=False)
            .values('account_id')
            .annotate(debit=Sum('debit'), credit=Sum('credit'))
        )
        bal = {row['account_id']: (row['debit'] or 0, row['credit'] or 0) for row in lines}

        accounts = list(Account.objects.all())
        for account in accounts:
            d, c = bal.get(account.pk, (0, 0))
            if account.account_type in ('asset', 'expense'):
                account.current_balance = account.opening_balance + d - c
            else:
                account.current_balance = account.opening_balance + c - d
        Account.objects.bulk_update(accounts, ['current_balance'])

        # العملاء: رصيد = مجموع (الإجمالي - المدفوع) للفواتير المرحّلة
        customers = list(Customer.objects.prefetch_related('salesinvoice_set'))
        for c in customers:
            c.current_balance = sum((i.total_amount - i.paid_amount) for i in c.salesinvoice_set.all() if i.is_posted)
        Customer.objects.bulk_update(customers, ['current_balance'])

        # الموردون
        suppliers = list(Supplier.objects.prefetch_related('purchaseinvoice_set'))
        for s in suppliers:
            s.current_balance = sum(
                (i.total_amount - i.paid_amount) for i in s.purchaseinvoice_set.all() if i.is_posted
            )
        Supplier.objects.bulk_update(suppliers, ['current_balance'])

        # المنتجات: المخزون من حركات الأسهم (تحميل دفعة واحدة عبر prefetch)
        products = list(Product.objects.prefetch_related('stock_movements'))
        for product in products:
            total = 0
            for m in product.stock_movements.all():
                if m.movement_type == 'in':
                    total += m.quantity
                elif m.movement_type == 'out':
                    total -= m.quantity
                elif m.movement_type == 'adjustment':
                    total = m.quantity
            product.current_stock = max(0, total)
        Product.objects.bulk_update(products, ['current_stock'])
    except Exception as e:
        logger.exception('Recalculate balances error: %s', e)
        raise


def create_sync_log(source_machine, sync_type, status='pending'):
    return SyncLog.objects.create(source_machine=source_machine, sync_type=sync_type, status=status)
