from django.urls import path

from . import views

app_name = 'budget'

urlpatterns = [
    path('cost-centers/', views.cost_center_list, name='cost_center_list'),
    path('cost-centers/create/', views.cost_center_create, name='cost_center_create'),
    path('cost-centers/<uuid:pk>/', views.cost_center_detail, name='cost_center_detail'),
    path('cost-centers/<uuid:pk>/edit/', views.cost_center_edit, name='cost_center_edit'),
    path('cost-centers/<uuid:pk>/delete/', views.cost_center_delete, name='cost_center_delete'),
    path('', views.budget_list, name='budget_list'),
    path('create/', views.budget_create, name='budget_create'),
    path('<uuid:pk>/', views.budget_detail, name='budget_detail'),
    path('<uuid:pk>/edit/', views.budget_edit, name='budget_edit'),
    path('<uuid:pk>/delete/', views.budget_delete, name='budget_delete'),
    path('report/', views.budget_report, name='budget_report'),
]
