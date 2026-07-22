from django.urls import path

from purchases import views as purchases_views

from . import views

app_name = 'warehouses'

urlpatterns = [
    path('', views.warehouse_list, name='warehouse_list'),
    path('create/', views.warehouse_create, name='warehouse_create'),
    path('<uuid:pk>/', views.warehouse_detail, name='warehouse_detail'),
    path('<uuid:pk>/edit/', views.warehouse_edit, name='warehouse_edit'),
    path('<uuid:pk>/product/add/', views.warehouse_product_add, name='warehouse_product_add'),
    path('movements/', views.movement_list, name='movement_list'),
    path('movements/create/', views.movement_create, name='movement_create'),
    path('movements/<uuid:pk>/', views.movement_detail, name='movement_detail'),
    # إدارة المنتجات (نُقلت من المشتريات إلى المستودعات)
    path('products/', purchases_views.product_list, name='product_list'),
    path('products/create/', purchases_views.product_create, name='product_create'),
    path('products/<uuid:pk>/edit/', purchases_views.product_edit, name='product_edit'),
    path('products/<uuid:pk>/barcode/', purchases_views.product_barcode_print, name='product_barcode'),
    path('products/barcode-batch/', purchases_views.product_barcode_batch, name='product_barcode_batch'),
    path('products/price-list/', purchases_views.product_price_list, name='product_price_list'),
    path('products/export/', purchases_views.export_products, name='export_products'),
    path('products/import/', purchases_views.import_products, name='import_products'),
]
