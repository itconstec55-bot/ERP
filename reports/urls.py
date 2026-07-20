from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list, name='report_list'),
    path('financial/', views.financial_dashboard, name='financial_dashboard'),
    path('workflow/', views.workflow_tracker, name='workflow_tracker'),
    path('income-statement/', views.income_statement, name='income_statement'),
    path('balance-sheet/', views.balance_sheet, name='balance_sheet'),
    path('trial-balance/', views.trial_balance_report, name='trial_balance_report'),
    path('general-ledger/', views.general_ledger, name='general_ledger'),
    path('vat-return/', views.vat_return, name='vat_return'),
    path('withholding-tax/', views.withholding_tax_report, name='withholding_tax_report'),
    path('supplier-report/', views.supplier_report, name='supplier_report'),
    path('supplier-report/<uuid:supplier_id>/', views.supplier_detail_report, name='supplier_detail_report'),
    path('customer-report/', views.customer_report, name='customer_report'),
    path('customer-report/<uuid:customer_id>/', views.customer_detail_report, name='customer_detail_report'),
    path('profit-margin/', views.profit_margin_report, name='profit_margin_report'),
    path('asset-schedule/', views.asset_schedule, name='asset_schedule'),
    path('payroll-report/', views.payroll_report, name='payroll_report'),
    path('ar-aging/', views.ar_aging_report, name='ar_aging_report'),
    path('ap-aging/', views.ap_aging_report, name='ap_aging_report'),
    path('inventory/', views.inventory_report, name='inventory_report'),
    path('stock-valuation/', views.stock_valuation_report, name='stock_valuation_report'),
    path('customer-statement/', views.customer_statement, name='customer_statement'),
    path('supplier-statement/', views.supplier_statement, name='supplier_statement'),
    path('daily-sales/', views.daily_sales_report, name='daily_sales_report'),
    path('daily-purchases/', views.daily_purchases_report, name='daily_purchases_report'),
    path('cash-flow/', views.cash_flow_report, name='cash_flow_report'),
    path('budget-vs-actual/', views.budget_vs_actual, name='budget_vs_actual'),
    path('bank-reconciliation/', views.bank_reconciliation_statement, name='bank_reconciliation_statement'),
    path('tax-summary/', views.tax_summary, name='tax_summary'),
    path('payroll-detail/', views.payroll_detail, name='payroll_detail'),
    path('export/<str:report_type>/', views.export_report, name='export_report'),
]
