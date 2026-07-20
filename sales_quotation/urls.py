from django.urls import path
from . import views

app_name = 'sales_quotation'

urlpatterns = [
    path('', views.quotation_list, name='quotation_list'),
    path('create/', views.quotation_create, name='quotation_create'),
    path('<uuid:pk>/', views.quotation_detail, name='quotation_detail'),
    path('<uuid:pk>/edit/', views.quotation_edit, name='quotation_edit'),
    path('<uuid:pk>/send/', views.quotation_send, name='quotation_send'),
    path('<uuid:pk>/accept/', views.quotation_accept, name='quotation_accept'),
    path('<uuid:pk>/reject/', views.quotation_reject, name='quotation_reject'),
    path('<uuid:pk>/to-invoice/', views.quotation_to_invoice, name='quotation_to_invoice'),
    path('<uuid:pk>/delete/', views.quotation_delete, name='quotation_delete'),
]
