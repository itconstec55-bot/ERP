from django.urls import path

from . import views

app_name = 'sales_returns'

urlpatterns = [
    path('', views.sales_return_list, name='list'),
    path('create/', views.sales_return_create, name='create'),
    path('<uuid:pk>/', views.sales_return_detail, name='detail'),
    path('<uuid:pk>/post/', views.sales_return_post, name='post'),
    path('<uuid:pk>/delete/', views.sales_return_delete, name='delete'),
]
