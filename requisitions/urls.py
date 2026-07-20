from django.urls import path
from . import views

app_name = 'requisitions'

urlpatterns = [
    path('', views.req_list, name='req_list'),
    path('create/', views.req_create, name='req_create'),
    path('<uuid:pk>/', views.req_detail, name='req_detail'),
    path('<uuid:pk>/edit/', views.req_edit, name='req_edit'),
    path('<uuid:pk>/submit/', views.req_submit, name='req_submit'),
    path('<uuid:pk>/approve/', views.req_approve, name='req_approve'),
    path('<uuid:pk>/reject/', views.req_reject, name='req_reject'),
    path('<uuid:pk>/convert/', views.req_convert, name='req_convert'),
    path('dashboard/', views.workflow_dashboard, name='workflow_dashboard'),
    path('pending/', views.pending_approvals, name='pending_approvals'),
]
