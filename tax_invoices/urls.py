from django.urls import path
from . import views

app_name = 'tax_invoices'

urlpatterns = [
    path('', views.tax_dashboard, name='dashboard'),
    path('connections/', views.connection_list, name='connection_list'),
    path('connections/create/', views.connection_create, name='connection_create'),
    path('connections/<uuid:pk>/edit/', views.connection_edit, name='connection_edit'),
    path('invoices/', views.tax_invoice_list, name='tax_invoice_list'),
    path('invoices/<uuid:pk>/', views.tax_invoice_detail, name='tax_invoice_detail'),
    path('invoices/create-from/<uuid:sales_pk>/', views.tax_invoice_create_from_sales,
         name='tax_invoice_create_from_sales'),
    path('invoices/<uuid:pk>/check-status/', views.tax_invoice_check_status,
         name='tax_invoice_check_status'),
    path('invoices/<uuid:pk>/void/', views.tax_invoice_void,
         name='tax_invoice_void'),
]
