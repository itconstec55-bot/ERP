from django.urls import path
from . import views

app_name = 'company'

urlpatterns = [
    path('', views.company_settings, name='company_settings'),
    path('branch/create/', views.branch_create, name='branch_create'),
    path('branch/<uuid:pk>/edit/', views.branch_edit, name='branch_edit'),
    path('branch/<uuid:pk>/delete/', views.branch_delete, name='branch_delete'),
    
    # Admin Settings Panel
    path('admin/settings/', views.admin_settings_dashboard, name='admin_settings'),
    
    # Account Type API
    path('admin/settings/account-types/create/', views.account_type_create, name='account_type_create'),
    path('admin/settings/account-types/<uuid:pk>/update/', views.account_type_update, name='account_type_update'),
    path('admin/settings/account-types/<uuid:pk>/delete/', views.account_type_delete, name='account_type_delete'),
    
    # Product API
    path('admin/settings/products/create/', views.product_create, name='product_create'),
    path('admin/settings/products/<uuid:pk>/update/', views.product_update, name='product_update'),
    path('admin/settings/products/<uuid:pk>/delete/', views.product_delete, name='product_delete'),
    
    # Category API
    path('admin/settings/categories/create/', views.category_create, name='category_create'),
    path('admin/settings/categories/<uuid:pk>/update/', views.category_update, name='category_update'),
    path('admin/settings/categories/<uuid:pk>/delete/', views.category_delete, name='category_delete'),
    
    # Unit of Measure API
    path('admin/settings/units/create/', views.unit_create, name='unit_create'),
    path('admin/settings/units/<uuid:pk>/update/', views.unit_update, name='unit_update'),
    path('admin/settings/units/<uuid:pk>/delete/', views.unit_delete, name='unit_delete'),
]
