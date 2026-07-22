from django.urls import path

from . import views

app_name = 'purchases'

urlpatterns = [
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/create/', views.supplier_create, name='supplier_create'),
    path('suppliers/<uuid:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<uuid:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('invoices/', views.purchase_invoice_list, name='invoice_list'),
    path('invoices/bulk-approve/', views.purchase_invoice_bulk_approve, name='invoice_bulk_approve'),
    path('invoices/bulk-post/', views.purchase_invoice_bulk_post, name='invoice_bulk_post'),
    path('invoices/create/', views.purchase_invoice_create, name='invoice_create'),
    path('invoices/<uuid:pk>/', views.purchase_invoice_detail, name='invoice_detail'),
    path('invoices/<uuid:pk>/post/', views.purchase_invoice_post, name='invoice_post'),
    path('invoices/<uuid:pk>/approve/', views.purchase_invoice_approve, name='invoice_approve'),
    path('invoices/<uuid:pk>/print/', views.purchase_invoice_print, name='invoice_print'),
    path('invoices/<uuid:pk>/whatsapp/', views.purchase_invoice_whatsapp, name='invoice_whatsapp'),
    path('suppliers/<uuid:pk>/whatsapp/', views.supplier_statement_whatsapp, name='supplier_statement_whatsapp'),
    path('suppliers/export/', views.export_suppliers, name='export_suppliers'),
    path('suppliers/import/', views.import_suppliers, name='import_suppliers'),
    path('products/export/', views.export_products, name='export_products'),
    path('products/import/', views.import_products, name='import_products'),
    path('products/', views.product_list, name='product_list'),
    path('settings/', views.catalog_settings, name='catalog_settings'),
]
