from django.core.management.base import BaseCommand
from django.db import transaction

from access_control.models import Role, Screen, RoleScreenPermission

SCREENS = [
    ('accounts.account', 'دليل الحسابات', 'الحسابات', 10),
    ('accounts.journalentry', 'القيود المحاسبية', 'الحسابات', 20),
    ('sales.customer', 'العملاء', 'المبيعات', 10),
    ('sales.invoice', 'فواتير المبيعات', 'المبيعات', 20),
    ('purchases.supplier', 'الموردون', 'المشتريات', 10),
    ('purchases.invoice', 'فواتير المشتريات', 'المشتريات', 20),
    ('purchases.product', 'الأصناف', 'المخازن', 5),
    ('warehouses.warehouse', 'المخازن', 'المخازن', 10),
    ('warehouses.stockmovement', 'حركات المخزون', 'المخازن', 20),
    ('treasury.safe', 'الخزائن', 'الخزينة', 10),
    ('treasury.bank', 'البنوك', 'الخزينة', 20),
    ('hr.employee', 'الموظفون', 'الموارد البشرية', 10),
    ('reports.report', 'التقارير', 'التقارير', 10),
    ('budget.budget', 'الموازنات', 'الميزانية', 10),
    ('requisitions.requisition', 'طلبات الشراء', 'المشتريات', 30),
    ('purchase_orders.purchaseorder', 'أوامر الشراء', 'المشتريات', 40),
    ('rfq.rfq', 'طلبات عروض الأسعار', 'المشتريات', 50),
    ('goods_received.grn', 'إذون الاستلام', 'المشتريات', 60),
    ('purchase_returns.purchasereturn', 'مرتجعات المشتريات', 'المشتريات', 70),
    ('sales_orders.salesorder', 'أوامر البيع', 'المبيعات', 30),
    ('sales_returns.salesreturn', 'مرتجعات المبيعات', 'المبيعات', 40),
    ('tax_invoices.taxinvoice', 'الفواتير الضريبية', 'المبيعات', 50),
    ('credit_notes.creditnote', 'إشعارات الخصم', 'الحسابات', 30),
    ('payment_receipts.paymentreceipt', 'سندات القبض والصرف', 'الخزينة', 30),
    ('cheques.cheque', 'الشيكات', 'الخزينة', 40),
    ('stock_adjustments.adjustment', 'تسويات المخزون', 'المخازن', 30),
    ('assets.asset', 'الأصول الثابتة', 'الأصول', 10),
    ('contractors.contractor', 'المقاولون والعقود', 'المقاولات', 10),
    ('concrete_production.production', 'إنتاج الخرسانة', 'الإنتاج', 10),
    ('currency.currency', 'العملات وأسعار الصرف', 'الإعدادات', 20),
    ('documents.document', 'المستندات', 'المستندات', 10),
    ('bank_reconciliation.statement', 'التسوية البنكية', 'الخزينة', 50),
    ('system.users', 'المستخدمون والمجموعات', 'النظام', 10),
    ('ai_analysis.errorlog', 'تحليل الأخطاء الذكي', 'النظام', 80),
    ('system.factory_reset', 'استعادة ضبط المصنع', 'النظام', 90),
]

ALL = dict.fromkeys(('view', 'add', 'edit', 'delete', 'print', 'export'), True)
READ = {'view': True, 'print': True, 'export': True}
OPERATE = {'view': True, 'add': True, 'edit': True, 'print': True, 'export': True}

ROLES = {
    'admin': ('مدير النظام', {'*': ALL}),
    'accountant': ('محاسب', {
        'accounts.account': OPERATE, 'accounts.journalentry': OPERATE,
        'treasury.safe': OPERATE, 'treasury.bank': OPERATE,
        'reports.report': READ, 'budget.budget': READ,
        'credit_notes.creditnote': OPERATE,
        'payment_receipts.paymentreceipt': OPERATE,
        'cheques.cheque': OPERATE, 'assets.asset': OPERATE,
    }),
    'warehouse_keeper': ('أمين مخزن', {
        'warehouses.warehouse': READ, 'warehouses.stockmovement': OPERATE,
        'purchases.product': READ, 'requisitions.requisition': OPERATE,
        'goods_received.grn': OPERATE,
        'purchase_returns.purchasereturn': OPERATE,
        'stock_adjustments.adjustment': OPERATE,
    }),
    'sales': ('مبيعات', {
        'sales.customer': OPERATE, 'sales.invoice': OPERATE,
        'reports.report': READ,
        'sales_orders.salesorder': OPERATE,
        'sales_returns.salesreturn': OPERATE,
        'tax_invoices.taxinvoice': OPERATE,
    }),
    'viewer': ('مشاهدة فقط', {'*': READ}),
}


class Command(BaseCommand):
    help = 'يزرع الشاشات والأدوار النظامية الافتراضية لإطار الصلاحيات'

    @transaction.atomic
    def handle(self, *args, **options):
        screen_map = {}
        for code, name, module, order in SCREENS:
            screen, _ = Screen.objects.update_or_create(
                code=code,
                defaults={'name': name, 'module': module, 'order': order, 'is_active': True},
            )
            screen_map[code] = screen
        self.stdout.write(self.style.SUCCESS(f'Screens seeded: {len(screen_map)}'))

        for code, (name, perms) in ROLES.items():
            role, _ = Role.objects.update_or_create(
                code=code,
                defaults={'name': name, 'is_system': True, 'is_active': True},
            )
            if '*' in perms:
                flags = perms['*']
                for screen in screen_map.values():
                    self._set(role, screen, flags)
            else:
                for scode, flags in perms.items():
                    screen = screen_map.get(scode)
                    if screen:
                        self._set(role, screen, flags)
        self.stdout.write(self.style.SUCCESS(f'System roles seeded: {len(ROLES)}'))

    @staticmethod
    def _set(role, screen, flags):
        RoleScreenPermission.objects.update_or_create(
            role=role, screen=screen,
            defaults={
                'grant_type': 'allow',
                'can_view': flags.get('view', False),
                'can_add': flags.get('add', False),
                'can_edit': flags.get('edit', False),
                'can_delete': flags.get('delete', False),
                'can_print': flags.get('print', False),
                'can_export': flags.get('export', False),
            },
        )
