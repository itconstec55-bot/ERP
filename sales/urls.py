from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/create/', views.customer_create, name='customer_create'),
    path('customers/<uuid:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<uuid:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('invoices/', views.sales_invoice_list, name='invoice_list'),
    path('invoices/bulk-approve/', views.sales_invoice_bulk_approve, name='invoice_bulk_approve'),
    path('invoices/bulk-post/', views.sales_invoice_bulk_post, name='invoice_bulk_post'),
    path('invoices/create/', views.sales_invoice_create, name='invoice_create'),
    path('invoices/<uuid:pk>/', views.sales_invoice_detail, name='invoice_detail'),
    path('invoices/<uuid:pk>/post/', views.sales_invoice_post, name='invoice_post'),
    path('invoices/<uuid:pk>/approve/', views.sales_invoice_approve, name='invoice_approve'),
    path('invoices/<uuid:pk>/print/', views.sales_invoice_print, name='invoice_print'),
    path('invoices/<uuid:pk>/whatsapp/', views.sales_invoice_whatsapp, name='invoice_whatsapp'),
    path('customers/<uuid:pk>/whatsapp/', views.customer_statement_whatsapp, name='customer_statement_whatsapp'),
    path('customers/export/', views.export_customers, name='export_customers'),
    path('customers/import/', views.import_customers, name='import_customers'),
]
