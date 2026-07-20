"""
URLs for common app - WhatsApp webhook endpoints + global search
"""
from django.urls import path
from .views import whatsapp_webhook, global_search

urlpatterns = [
    path('whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path('search/', global_search, name='search'),
]