"""
URLs for common app - WhatsApp webhook endpoints + global search
"""

from django.urls import path

from .views import global_search, whatsapp_webhook

urlpatterns = [
    path('whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path('search/', global_search, name='search'),
]
