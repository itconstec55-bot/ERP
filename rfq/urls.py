from django.urls import path
from . import views

app_name = 'rfq'

urlpatterns = [
    path('', views.rfq_list, name='rfq_list'),
    path('create/', views.rfq_create, name='rfq_create'),
    path('pending/', views.pending_quotations, name='pending_quotations'),
    path('<uuid:pk>/', views.rfq_detail, name='rfq_detail'),
    path('<uuid:pk>/edit/', views.rfq_edit, name='rfq_edit'),
    path('<uuid:pk>/send/', views.rfq_send, name='rfq_send'),
    path('<uuid:pk>/close/', views.rfq_close, name='rfq_close'),
    path('<uuid:pk>/convert/', views.rfq_convert_to_po, name='rfq_convert_to_po'),
    path('<uuid:pk>/quotation/create/', views.quotation_create, name='quotation_create'),
    path('quotation/<uuid:pk>/accept/', views.quotation_accept, name='quotation_accept'),
]
