from django.urls import path

from . import views

app_name = 'bank_reconciliation'

urlpatterns = [
    path('', views.reconciliation_dashboard, name='dashboard'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<uuid:pk>/', views.session_detail, name='session_detail'),
    path('items/', views.item_list, name='item_list'),
    path('items/create/', views.item_create, name='item_create'),
    path('items/<uuid:pk>/match/', views.item_match, name='item_match'),
    path('items/<uuid:pk>/unmatch/', views.item_unmatch, name='item_unmatch'),
    path('items/<uuid:pk>/delete/', views.item_delete, name='item_delete'),
    path('import-csv/', views.import_csv, name='import_csv'),
    path('auto-match/', views.auto_match, name='auto_match'),
]
