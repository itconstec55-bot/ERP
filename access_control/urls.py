from django.urls import path

from . import views

app_name = 'access_control'

urlpatterns = [
    path('', views.permission_dashboard, name='dashboard'),
    path('user/<int:pk>/', views.user_permission_detail, name='user_detail'),
    path('user/<int:pk>/assign-role/', views.user_assign_role, name='user_assign_role'),
    path('user/<int:pk>/remove-role/<uuid:assignment_pk>/', views.user_remove_role, name='user_remove_role'),
    path('user/<int:pk>/branch/add/', views.user_add_branch, name='user_add_branch'),
    path('user/<int:pk>/branch/remove/<uuid:item_pk>/', views.user_remove_branch, name='user_remove_branch'),
    path('user/<int:pk>/warehouse/add/', views.user_add_warehouse, name='user_add_warehouse'),
    path('user/<int:pk>/warehouse/remove/<uuid:item_pk>/', views.user_remove_warehouse, name='user_remove_warehouse'),
    path('user/<int:pk>/account-type/add/', views.user_add_account_type, name='user_add_account_type'),
    path(
        'user/<int:pk>/account-type/remove/<uuid:item_pk>/',
        views.user_remove_account_type,
        name='user_remove_account_type',
    ),
    path('user/<int:pk>/scope-flags/', views.user_update_scope_flags, name='user_update_scope_flags'),
    path('user/<int:pk>/exception/set/', views.user_set_screen_exception, name='user_set_screen_exception'),
    path(
        'user/<int:pk>/exception/remove/<uuid:item_pk>/',
        views.user_remove_screen_exception,
        name='user_remove_screen_exception',
    ),
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<uuid:pk>/', views.role_edit, name='role_edit'),
    path('roles/<uuid:pk>/delete/', views.role_delete, name='role_delete'),
]
