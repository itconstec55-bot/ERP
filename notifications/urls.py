from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_dashboard, name='dashboard'),
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('send-test/', views.send_test_notification, name='send_test'),
]
