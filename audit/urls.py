from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('', views.audit_log_list, name='audit_log_list'),
    path('export/', views.audit_export, name='audit_export'),
]
