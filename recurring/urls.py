from django.urls import path
from . import views

app_name = 'recurring'

urlpatterns = [
    path('', views.recurring_list, name='recurring_list'),
    path('create/', views.recurring_create, name='recurring_create'),
    path('<uuid:pk>/', views.recurring_detail, name='recurring_detail'),
    path('<uuid:pk>/edit/', views.recurring_edit, name='recurring_edit'),
    path('<uuid:pk>/execute/', views.recurring_execute, name='recurring_execute'),
    path('<uuid:pk>/toggle/', views.recurring_toggle, name='recurring_toggle'),
    path('<uuid:pk>/delete/', views.recurring_delete, name='recurring_delete'),
]
