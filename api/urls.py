from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.trailing_slash = ''

# ─── Core Accounting ───
router.register('account-types', views.AccountTypeViewSet, basename='account-types')
router.register('accounts', views.AccountViewSet, basename='accounts')
router.register('journal-entries', views.JournalEntryViewSet, basename='journal-entries')

# ─── Purchases ───
router.register('suppliers', views.SupplierViewSet, basename='suppliers')
router.register('products', views.ProductViewSet, basename='products')
router.register('product-categories', views.ProductCategoryViewSet, basename='product-categories')
router.register('units', views.UnitOfMeasureViewSet, basename='units')
router.register('purchase-invoices', views.PurchaseInvoiceViewSet, basename='purchase-invoices')

# ─── Sales ───
router.register('customers', views.CustomerViewSet, basename='customers')
router.register('sales-invoices', views.SalesInvoiceViewSet, basename='sales-invoices')

# ─── Treasury ───
router.register('banks', views.BankViewSet, basename='banks')
router.register('safes', views.SafeViewSet, basename='safes')
router.register('bank-transactions', views.BankTransactionViewSet, basename='bank-transactions')
router.register('safe-transactions', views.SafeTransactionViewSet, basename='safe-transactions')

# ─── HR ───
router.register('departments', views.DepartmentViewSet, basename='departments')
router.register('employees', views.EmployeeViewSet, basename='employees')
router.register('attendance', views.AttendanceViewSet, basename='attendance')
router.register('salaries', views.SalaryViewSet, basename='salaries')

# ─── Assets ───
router.register('asset-categories', views.AssetCategoryViewSet, basename='asset-categories')
router.register('assets', views.AssetViewSet, basename='assets')
router.register('depreciation-entries', views.DepreciationEntryViewSet, basename='depreciation-entries')

# ─── Warehouses / Inventory ───
router.register('warehouses', views.WarehouseViewSet, basename='warehouses')
router.register('warehouse-products', views.WarehouseProductViewSet, basename='warehouse-products')
router.register('stock-movements', views.StockMovementViewSet, basename='stock-movements')
router.register('stock-adjustments', views.StockAdjustmentViewSet, basename='stock-adjustments')

# ─── Company ───
router.register('company', views.CompanyViewSet, basename='company')
router.register('branches', views.CompanyBranchViewSet, basename='branches')

# ─── Budget ───
router.register('cost-centers', views.CostCenterViewSet, basename='cost-centers')
router.register('budgets', views.BudgetViewSet, basename='budgets')

# ─── Currency ───
router.register('currencies', views.CurrencyViewSet, basename='currencies')
router.register('exchange-rates', views.ExchangeRateHistoryViewSet, basename='exchange-rates')

# ─── Documents ───
router.register('document-types', views.DocumentTypeViewSet, basename='document-types')
router.register('document-templates', views.DocumentTemplateViewSet, basename='document-templates')
router.register('documents', views.DocumentViewSet, basename='documents')

# ─── Audit ───
router.register('audit-logs', views.AuditLogViewSet, basename='audit-logs')

# ─── Cheques ───
router.register('cheques', views.ChequeViewSet, basename='cheques')

# ─── Credit Notes ───
router.register('credit-notes', views.CreditNoteViewSet, basename='credit-notes')

# ─── Returns ───
router.register('sales-returns', views.SalesReturnViewSet, basename='sales-returns')
router.register('purchase-returns', views.PurchaseReturnViewSet, basename='purchase-returns')

# ─── Payment Receipts ───
router.register('payment-receipts', views.PaymentReceiptViewSet, basename='payment-receipts')

# ─── Tax Invoices / ETA ───
router.register('eta-connections', views.ETAConnectionViewSet, basename='eta-connections')
router.register('tax-invoices', views.TaxInvoiceViewSet, basename='tax-invoices')

# ─── Purchase Orders ───
router.register('purchase-orders', views.PurchaseOrderViewSet, basename='purchase-orders')

# ─── Sales Orders ───
router.register('sales-orders', views.SalesOrderViewSet, basename='sales-orders')

# ─── Goods Received ───
router.register('goods-received', views.GoodsReceivedNoteViewSet, basename='goods-received')

# ─── Requisitions ───
router.register('requisitions', views.RequisitionViewSet, basename='requisitions')

# ─── RFQ / Quotations ───
router.register('rfq', views.RFQViewSet, basename='rfq')
router.register('quotations', views.QuotationViewSet, basename='quotations')

# ─── Contractors ───
router.register('contractors', views.ContractorViewSet, basename='contractors')
router.register('contracts', views.ContractViewSet, basename='contracts')
router.register('interim-certificates', views.InterimCertificateViewSet, basename='interim-certificates')
router.register('contractor-payments', views.ContractorPaymentViewSet, basename='contractor-payments')

# ─── Recurring ───
router.register('recurring-journals', views.RecurringJournalViewSet, basename='recurring-journals')

# ─── Notifications ───
router.register('notification-categories', views.NotificationCategoryViewSet, basename='notification-categories')
router.register('notification-templates', views.NotificationTemplateViewSet, basename='notification-templates')
router.register('notification-logs', views.NotificationLogViewSet, basename='notification-logs')

# ─── Users (read-only) ───
router.register('users', views.UserViewSet, basename='users')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', views.api_login, name='api-login'),
    path('dashboard/', views.api_dashboard, name='api-dashboard'),
    path('stock-summary/', views.api_stock_summary, name='api-stock-summary'),
]
