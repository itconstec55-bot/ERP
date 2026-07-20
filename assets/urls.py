from django.urls import path
from . import views

app_name = 'assets'

urlpatterns = [
    path('', views.asset_list, name='asset_list'),
    path('create/', views.asset_create, name='asset_create'),
    path('<uuid:pk>/', views.asset_detail, name='asset_detail'),
    path('<uuid:pk>/edit/', views.asset_edit, name='asset_edit'),
    path('<uuid:asset_id>/depreciation/', views.depreciation_create, name='depreciation_create'),
    path('categories/', views.asset_category_list, name='category_list'),
    path('categories/create/', views.asset_category_create, name='category_create'),
    path('export/assets/', views.export_assets, name='export_assets'),
    path('import/assets/', views.import_assets, name='import_assets'),
    path('<uuid:pk>/dispose/', views.asset_dispose, name='asset_dispose'),
]
