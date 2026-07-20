from rest_framework.permissions import BasePermission


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff


class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if hasattr(obj, 'created_by') and obj.created_by:
            return obj.created_by == request.user
        return request.user.is_staff


class ModulePermission(BasePermission):
    """Check screen-based permissions matching access_control module."""
    MODULE_MAP = {
        'accounts': ('accounts.account', 'view'),
        'account-types': ('accounts.account', 'edit'),
        'journal-entries': ('accounts.account', 'edit'),
        'suppliers': ('purchases.supplier', 'view'),
        'products': ('purchases.product', 'view'),
        'product-categories': ('purchases.product', 'view'),
        'units': ('purchases.product', 'view'),
        'purchase-invoices': ('purchases.purchaseinvoice', 'view'),
        'customers': ('sales.customer', 'view'),
        'sales-invoices': ('sales.salesinvoice', 'view'),
        'banks': ('treasury.bank', 'view'),
        'safes': ('treasury.safe', 'view'),
        'bank-transactions': ('treasury.banktransaction', 'view'),
        'safe-transactions': ('treasury.safetransaction', 'view'),
        'employees': ('hr.employee', 'view'),
        'departments': ('hr.department', 'view'),
        'salaries': ('hr.salary', 'view'),
        'attendance': ('hr.attendance', 'view'),
        'assets': ('assets.asset', 'view'),
        'asset-categories': ('assets.assetcategory', 'view'),
        'depreciation-entries': ('assets.depreciationentry', 'view'),
        'warehouses': ('warehouses.warehouse', 'view'),
        'warehouse-products': ('warehouses.warehouseproduct', 'view'),
        'stock-movements': ('warehouses.stockmovement', 'view'),
        'stock-adjustments': ('stock_adjustments.stockadjustment', 'view'),
        'cost-centers': ('budget.costcenter', 'view'),
        'budgets': ('budget.budget', 'view'),
        'documents': ('documents.document', 'view'),
        'document-types': ('documents.documenttype', 'view'),
        'document-templates': ('documents.documenttemplate', 'view'),
        'audit-logs': ('audit.auditlog', 'view'),
        'cheques': ('cheques.cheque', 'view'),
        'credit-notes': ('credit_notes.creditnote', 'view'),
        'payment-receipts': ('payment_receipts.paymentreceipt', 'view'),
        'sales-returns': ('sales_returns.salesreturn', 'view'),
        'purchase-returns': ('purchase_returns.purchasereturn', 'view'),
        'tax-invoices': ('tax_invoices.taxinvoice', 'view'),
        'eta-connections': ('tax_invoices.etaconnection', 'view'),
        'purchase-orders': ('purchase_orders.purchaseorder', 'view'),
        'sales-orders': ('sales_orders.salesorder', 'view'),
        'goods-received': ('goods_received.goodsreceivednote', 'view'),
        'requisitions': ('requisitions.requisition', 'view'),
        'rfq': ('rfq.rfq', 'view'),
        'quotations': ('rfq.quotation', 'view'),
        'currencies': ('currency.currency', 'view'),
        'exchange-rates': ('currency.exchangeratehistory', 'view'),
        'company': ('company.company', 'view'),
        'branches': ('company.companybranch', 'view'),
        'contractors': ('contractors.contractor', 'view'),
        'contracts': ('contractors.contract', 'view'),
        'interim-certificates': ('contractors.interimcertificate', 'view'),
        'contractor-payments': ('contractors.contractorpayment', 'view'),
        'recurring-journals': ('recurring.recurringjournal', 'view'),
        'notification-categories': ('notifications.notificationcategory', 'view'),
        'notification-templates': ('notifications.notificationtemplate', 'view'),
        'notification-logs': ('notifications.notificationlog', 'view'),
        'users': ('auth.user', 'view'),
    }

    ACTION_MAP = {
        'list': 'view', 'retrieve': 'view',
        'create': 'add',
        'update': 'edit', 'partial_update': 'edit',
        'destroy': 'delete',
    }

    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        lookup = self.MODULE_MAP.get(view.base_name)
        if not lookup:
            return False
        action = self.ACTION_MAP.get(view.action, 'view')
        return request.user.has_screen_permission(lookup[0], action)


class IsAuthenticatedOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user and request.user.is_authenticated
