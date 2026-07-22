from django.contrib import admin

from .models import Backup, BackupSettings, FactoryResetRequest


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ['name', 'backup_type', 'file_size_display', 'status', 'created_by', 'created_at']
    list_filter = ['backup_type', 'status']
    readonly_fields = ['id', 'file_path', 'file_size', 'created_at']


@admin.register(BackupSettings)
class BackupSettingsAdmin(admin.ModelAdmin):
    list_display = ['auto_backup_enabled', 'backup_interval_hours', 'max_backups']


@admin.register(FactoryResetRequest)
class FactoryResetRequestAdmin(admin.ModelAdmin):
    """للاطلاع/المساءلة فقط — لا يُنشأ ولا يُعدَّل من هنا (المنطق عبر طبقة الخدمة)."""

    list_display = [
        'requested_at',
        'reset_scope',
        'status',
        'requested_by',
        'reviewed_by',
        'executed_by',
        'executed_at',
    ]
    list_filter = ['status', 'reset_scope']
    search_fields = ['reason', 'result_notes']
    readonly_fields = [f.name for f in FactoryResetRequest._meta.fields]
    ordering = ['-requested_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
