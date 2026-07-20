from django.urls import path

from . import views

app_name = 'sales_orders'

urlpatterns = [
    path('', views.so_list, name='so_list'),
    path('create/', views.so_create, name='so_create'),
    path('<uuid:pk>/', views.so_detail, name='so_detail'),
    path('<uuid:pk>/edit/', views.so_edit, name='so_edit'),
    path('<uuid:pk>/confirm/', views.so_confirm, name='so_confirm'),
    path('<uuid:pk>/cancel/', views.so_cancel, name='so_cancel'),
    path('<uuid:pk>/to-invoice/', views.so_to_invoice, name='so_to_invoice'),
]
