from django.urls import path

from . import views

app_name = 'documents'

urlpatterns = [
    path('types/', views.document_type_list, name='document_type_list'),
    path('types/create/', views.document_type_create, name='document_type_create'),
    path('types/<uuid:pk>/edit/', views.document_type_edit, name='document_type_edit'),
    path('templates/', views.document_template_list, name='document_template_list'),
    path('templates/create/', views.document_template_create, name='document_template_create'),
    path('templates/<uuid:pk>/edit/', views.document_template_edit, name='document_template_edit'),
    path('', views.document_list, name='document_list'),
    path('create/', views.document_create, name='document_create'),
    path('<uuid:pk>/', views.document_detail, name='document_detail'),
    path('<uuid:pk>/edit/', views.document_edit, name='document_edit'),
    path('<uuid:pk>/action/', views.document_action, name='document_action'),
    path('<uuid:pk>/attachment/', views.document_add_attachment, name='document_add_attachment'),
]
