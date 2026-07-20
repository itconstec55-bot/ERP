from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.account_list, name='account_list'),
    path('create/', views.account_create, name='account_create'),
    path('<uuid:pk>/', views.account_detail, name='account_detail'),
    path('<uuid:pk>/edit/', views.account_edit, name='account_edit'),
    path('<uuid:pk>/statement/', views.account_statement, name='account_statement'),
    path('journal/', views.journal_list, name='journal_list'),
    path('journal/create/', views.journal_create, name='journal_create'),
    path('journal/<uuid:pk>/', views.journal_detail, name='journal_detail'),
    path('journal/<uuid:pk>/edit/', views.journal_edit, name='journal_edit'),
    path('journal/<uuid:pk>/delete/', views.journal_delete, name='journal_delete'),
    path('journal/<uuid:pk>/post/', views.journal_post, name='journal_post'),
    path('trial-balance/', views.trial_balance, name='trial_balance'),
    path('chart-of-accounts/', views.chart_of_accounts, name='chart_of_accounts'),
    path('export/', views.export_accounts, name='export_accounts'),
    path('import/', views.import_accounts, name='import_accounts'),
    path('journal/export/', views.export_journal, name='export_journal'),
    path('fiscal-year-close/', views.fiscal_year_close, name='fiscal_year_close'),
]
