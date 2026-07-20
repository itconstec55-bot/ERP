from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.user_list, name='user_list'),
    path('create/', views.user_create, name='user_create'),
    path('<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('<int:pk>/password/', views.change_password, name='change_password'),
    # 2FA URLs
    path('2fa/setup/', views.two_factor_setup, name='two_factor_setup'),
    path('2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
    path('2fa/status/', views.two_factor_status, name='two_factor_status'),
    path('2fa/disable/', views.two_factor_disable, name='two_factor_disable'),
    # Session Management URLs
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/<str:session_key>/revoke/', views.session_revoke, name='session_revoke'),
    path('sessions/revoke-all/', views.session_revoke_all, name='session_revoke_all'),
]
