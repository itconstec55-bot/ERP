from django.urls import path

from . import views

app_name = 'credit_notes'

urlpatterns = [
    path('', views.credit_note_list, name='credit_note_list'),
    path('create/', views.credit_note_create, name='credit_note_create'),
    path('<uuid:pk>/', views.credit_note_detail, name='credit_note_detail'),
    path('<uuid:pk>/post/', views.credit_note_post, name='credit_note_post'),
    path('<uuid:pk>/delete/', views.credit_note_delete, name='credit_note_delete'),
]
