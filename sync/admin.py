from django.contrib import admin
from .models import MachineInfo, SyncLog, SyncSettings


@admin.register(MachineInfo)
class MachineInfoAdmin(admin.ModelAdmin):
    list_display = ['machine_id', 'name', 'machine_type', 'is_active', 'last_sync_at']
    list_filter = ['machine_type', 'is_active']


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['source_machine', 'sync_type', 'status', 'records_sent', 'records_received', 'started_at']
    list_filter = ['sync_type', 'status']


@admin.register(SyncSettings)
class SyncSettingsAdmin(admin.ModelAdmin):
    list_display = ['auto_sync_enabled', 'sync_interval_minutes', 'host_address']
