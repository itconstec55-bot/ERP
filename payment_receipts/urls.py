from django.urls import path
from . import views

app_name = 'payment_receipts'

urlpatterns = [
    path('', views.receipt_list, name='list'),
    path('create/', views.receipt_create, name='create'),
    path('<uuid:pk>/', views.receipt_detail, name='detail'),
    path('<uuid:pk>/post/', views.receipt_post, name='post'),
    path('<uuid:pk>/allocate/', views.receipt_allocate, name='allocate'),
    path('<uuid:pk>/delete/', views.receipt_delete, name='delete'),
    path('<uuid:pk>/print/', views.receipt_print, name='print'),
    path('api/customer-invoices/', views.get_customer_invoices, name='customer_invoices_api'),
    path('api/supplier-invoices/', views.get_supplier_invoices, name='supplier_invoices_api'),
]
