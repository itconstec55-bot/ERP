from django.urls import path

from . import views

app_name = 'backups'

urlpatterns = [
    path('', views.backup_dashboard, name='backup_dashboard'),
    path('create/', views.create_backup, name='create_backup'),
    path('<uuid:pk>/download/', views.download_backup, name='download_backup'),
    path('<uuid:pk>/delete/', views.delete_backup, name='delete_backup'),
    path('<uuid:pk>/restore/', views.restore_backup, name='restore_backup'),
    path('export-json/', views.export_json, name='export_json'),
    path('import-json/', views.import_json, name='import_json'),
    path('settings/', views.backup_settings_view, name='backup_settings'),
    # استعادة ضبط المصنع (اعتماد مزدوج)
    path('factory-reset/', views.factory_reset_home, name='factory_reset_home'),
    path('factory-reset/request/', views.factory_reset_request, name='factory_reset_request'),
    path('factory-reset/<uuid:pk>/approve/', views.factory_reset_approve, name='factory_reset_approve'),
    path('factory-reset/<uuid:pk>/reject/', views.factory_reset_reject, name='factory_reset_reject'),
    path('factory-reset/<uuid:pk>/cancel/', views.factory_reset_cancel, name='factory_reset_cancel'),
    path('factory-reset/<uuid:pk>/execute/', views.factory_reset_execute, name='factory_reset_execute'),
]
