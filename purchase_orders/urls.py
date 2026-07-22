from django.urls import path

from . import views

app_name = 'purchase_orders'

urlpatterns = [
    path('', views.po_list, name='po_list'),
    path('create/', views.po_create, name='po_create'),
    path('<uuid:pk>/', views.po_detail, name='po_detail'),
    path('<uuid:pk>/edit/', views.po_edit, name='po_edit'),
    path('<uuid:pk>/approve/', views.po_approve, name='po_approve'),
    path('<uuid:pk>/cancel/', views.po_cancel, name='po_cancel'),
    path('<uuid:pk>/to-invoice/', views.po_to_invoice, name='po_to_invoice'),
]
