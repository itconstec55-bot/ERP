from django.contrib import admin
from .models import ErrorLog, ErrorPattern, Solution


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ['title', 'error_type', 'severity', 'status', 'created_at']
    list_filter = ['severity', 'status', 'error_type']
    search_fields = ['title', 'description', 'reference_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ErrorPattern)
class ErrorPatternAdmin(admin.ModelAdmin):
    list_display = ['pattern_name', 'error_type', 'occurrence_count', 'is_active']
    list_filter = ['is_active', 'error_type']


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'error_log', 'applied', 'created_at']
    list_filter = ['priority', 'applied']
