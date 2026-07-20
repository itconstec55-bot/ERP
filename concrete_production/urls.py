from django.urls import path
from . import views

app_name = 'concrete_production'

urlpatterns = [
    # لوحة التحكم
    path('', views.dashboard, name='dashboard'),

    # تصاميم الخلطات
    path('mixes/', views.mix_design_list, name='mix_design_list'),
    path('mixes/create/', views.mix_design_create, name='mix_design_create'),
    path('mixes/<uuid:pk>/', views.mix_design_detail, name='mix_design_detail'),
    path('mixes/<uuid:pk>/edit/', views.mix_design_edit, name='mix_design_edit'),

    # طلبات العملاء
    path('requests/', views.customer_request_list, name='customer_request_list'),
    path('requests/create/', views.customer_request_create, name='customer_request_create'),
    path('requests/<uuid:pk>/', views.customer_request_detail, name='customer_request_detail'),
    path('requests/<uuid:pk>/confirm/', views.customer_request_confirm, name='customer_request_confirm'),

    # أوامر الإنتاج
    path('orders/', views.production_order_list, name='production_order_list'),
    path('orders/cost-per-m3/', views.production_cost_per_m3, name='production_cost_per_m3'),
    path('orders/daily/', views.production_daily, name='production_daily'),
    path('orders/create/', views.production_order_create, name='production_order_create'),
    path('orders/<uuid:pk>/', views.production_order_detail, name='production_order_detail'),
    path('orders/<uuid:pk>/schedule/', views.production_order_schedule, name='production_order_schedule'),

    # الدفعات الإنتاجية
    path('batches/', views.batch_list, name='batch_list'),
    path('batches/create/', views.batch_create, name='batch_create'),
    path('batches/<uuid:pk>/', views.batch_detail, name='batch_detail'),
    path('batches/<uuid:pk>/update-status/', views.batch_update_status, name='batch_update_status'),

    # الشاحنات
    path('trucks/', views.truck_list, name='truck_list'),
    path('trucks/create/', views.truck_create, name='truck_create'),
    path('trucks/<uuid:pk>/edit/', views.truck_edit, name='truck_edit'),

    # جدول التسليمات
    path('deliveries/', views.delivery_list, name='delivery_list'),
    path('deliveries/create/', views.delivery_create, name='delivery_create'),

    # تكاليف الإنتاج
    path('costs/', views.cost_list, name='cost_list'),
    path('costs/create/', views.cost_create, name='cost_create'),

    # API
    path('api/mix/<uuid:pk>/components/', views.api_mix_components, name='api_mix_components'),
    path('api/trucks/available/', views.api_available_trucks, name='api_available_trucks'),
    path('api/stats/', views.api_production_stats, name='api_production_stats'),

    # سيلو
    path('silos/', views.silo_dashboard, name='silo_dashboard'),
    path('silos/daily/', views.cement_daily_inventory, name='cement_daily_inventory'),
    path('silos/list/', views.silo_list, name='silo_list'),
    path('silos/create/', views.silo_create, name='silo_create'),
    path('silos/<uuid:pk>/', views.silo_detail, name='silo_detail'),
    path('silos/<uuid:pk>/edit/', views.silo_edit, name='silo_edit'),
    path('silos/<uuid:silo_pk>/transaction/', views.silo_transaction_create, name='silo_transaction_create'),
    path('api/silo/stock/', views.api_silo_stock, name='api_silo_stock'),
]
