from django.urls import path
from . import views

app_name = 'sync'

urlpatterns = [
    path('', views.sync_dashboard, name='sync_dashboard'),
    path('settings/', views.sync_settings_view, name='sync_settings'),
    path('test/', views.test_connection, name='test_connection'),
    path('manual/', views.manual_sync, name='manual_sync'),
    path('log/<uuid:pk>/', views.sync_log_detail, name='sync_log_detail'),
    path('api/push/', views.api_push, name='api_push'),
    path('api/pull/', views.api_pull, name='api_pull'),
    path('api/status/', views.api_status, name='api_status'),
    path('api/recalculate/', views.api_recalculate, name='api_recalculate'),
]
