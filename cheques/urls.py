from django.urls import path
from . import views

app_name = 'cheques'

urlpatterns = [
    path('', views.cheque_dashboard, name='cheque_dashboard'),
    path('list/', views.cheque_list, name='cheque_list'),
    path('create/', views.cheque_create, name='cheque_create'),
    path('<uuid:pk>/', views.cheque_detail, name='cheque_detail'),
    path('<uuid:pk>/update-status/', views.cheque_update_status, name='cheque_update_status'),
    path('<uuid:pk>/delete/', views.cheque_delete, name='cheque_delete'),
]
