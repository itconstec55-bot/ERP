from django.urls import path
from . import views

app_name = 'treasury'

urlpatterns = [
    path('banks/', views.bank_list, name='bank_list'),
    path('banks/create/', views.bank_create, name='bank_create'),
    path('banks/<uuid:pk>/', views.bank_detail, name='bank_detail'),
    path('banks/<uuid:pk>/edit/', views.bank_edit, name='bank_edit'),
    path('banks/<uuid:pk>/delete/', views.bank_delete, name='bank_delete'),
    path('banks/<uuid:bank_id>/transaction/', views.bank_transaction_create, name='bank_transaction_create'),
    path('safes/', views.safe_list, name='safe_list'),
    path('safes/create/', views.safe_create, name='safe_create'),
    path('safes/<uuid:pk>/', views.safe_detail, name='safe_detail'),
    path('safes/<uuid:pk>/edit/', views.safe_edit, name='safe_edit'),
    path('safes/<uuid:pk>/delete/', views.safe_delete, name='safe_delete'),
    path('safes/<uuid:safe_id>/transaction/', views.safe_transaction_create, name='safe_transaction_create'),
    path('export/banks/', views.export_banks, name='export_banks'),
    path('export/safes/', views.export_safes, name='export_safes'),
    path('import/banks/', views.import_banks, name='import_banks'),
    path('import/safes/', views.import_safes, name='import_safes'),
]
