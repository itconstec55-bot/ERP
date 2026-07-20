from django.contrib import admin
from .models import NotificationCategory, NotificationTemplate, NotificationLog


@admin.register(NotificationCategory)
class NotificationCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'is_active']
    list_filter = ['event', 'is_active']


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['subject', 'recipient_email', 'sent_at', 'success']
    list_filter = ['success']
