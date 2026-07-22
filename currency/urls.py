from django.urls import path

from . import views

app_name = 'currency'

urlpatterns = [
    path('', views.currency_list, name='currency_list'),
    path('create/', views.currency_create, name='currency_create'),
    path('<uuid:pk>/edit/', views.currency_edit, name='currency_edit'),
    path('rates/', views.exchange_rate_history, name='exchange_rate_history'),
]
