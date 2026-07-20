from django.urls import path

from . import views

app_name = 'purchase_returns'

urlpatterns = [
    path('', views.purchase_return_list, name='list'),
    path('create/', views.purchase_return_create, name='create'),
    path('<uuid:pk>/', views.purchase_return_detail, name='detail'),
    path('<uuid:pk>/post/', views.purchase_return_post, name='post'),
    path('<uuid:pk>/delete/', views.purchase_return_delete, name='delete'),
]
