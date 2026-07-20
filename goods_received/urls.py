from django.urls import path

from . import views

app_name = 'goods_received'

urlpatterns = [
    path('', views.grn_list, name='grn_list'),
    path('create/', views.grn_create, name='grn_create'),
    path('<uuid:pk>/', views.grn_detail, name='grn_detail'),
    path('<uuid:pk>/confirm/', views.grn_confirm, name='grn_confirm'),
    path('<uuid:pk>/to-invoice/', views.grn_to_invoice, name='grn_to_invoice'),
]
