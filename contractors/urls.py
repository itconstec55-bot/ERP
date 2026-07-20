from django.urls import path

from . import views

app_name = 'contractors'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    # المقاولون
    path('contractors/', views.contractor_list, name='contractor_list'),
    path('contractors/create/', views.contractor_create, name='contractor_create'),
    path('contractors/<uuid:pk>/', views.contractor_detail, name='contractor_detail'),
    path('contractors/<uuid:pk>/edit/', views.contractor_edit, name='contractor_edit'),
    # العقود
    path('contracts/', views.contract_list, name='contract_list'),
    path('contracts/create/', views.contract_create, name='contract_create'),
    path('contracts/<uuid:pk>/', views.contract_detail, name='contract_detail'),
    path('contracts/<uuid:pk>/edit/', views.contract_edit, name='contract_edit'),
    path('contracts/<uuid:pk>/approve/', views.contract_approve, name='contract_approve'),
    path('contracts/<uuid:pk>/close/', views.contract_close, name='contract_close'),
    # المستخلصات
    path('certificates/', views.certificate_list, name='certificate_list'),
    path('certificates/create/', views.certificate_create, name='certificate_create'),
    path('certificates/<uuid:pk>/', views.certificate_detail, name='certificate_detail'),
    path('certificates/<uuid:pk>/approve/', views.certificate_approve, name='certificate_approve'),
    path('certificates/<uuid:pk>/post/', views.certificate_post, name='certificate_post'),
    # المدفوعات
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/create/', views.payment_create, name='payment_create'),
    path('payments/<uuid:pk>/', views.payment_detail, name='payment_detail'),
    path('payments/<uuid:pk>/post/', views.payment_post, name='payment_post'),
    # API
    path('api/contract/<uuid:pk>/items/', views.api_contract_items, name='api_contract_items'),
    path('api/contractor/<uuid:pk>/stats/', views.api_contractor_stats, name='api_contractor_stats'),
]
