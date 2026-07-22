from django.urls import path

from . import views

app_name = 'stock_adjustments'

urlpatterns = [
    path('', views.adjustment_list, name='list'),
    path('create/', views.adjustment_create, name='create'),
    path('<uuid:pk>/', views.adjustment_detail, name='detail'),
    path('<uuid:pk>/approve/', views.adjustment_approve, name='approve'),
    path('<uuid:pk>/delete/', views.adjustment_delete, name='delete'),
]
