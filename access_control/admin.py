from django.contrib import admin

from .models import (
    Role, Screen, RoleScreenPermission, UserScreenPermission,
    UserRoleAssignment, UserBranch, UserWarehouse, UserAccountTypeScope,
)

_LEVEL_FIELDS = ('can_view', 'can_add', 'can_edit', 'can_delete', 'can_print', 'can_export')


class RoleScreenPermissionInline(admin.TabularInline):
    model = RoleScreenPermission
    extra = 0
    autocomplete_fields = ['screen']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_system', 'is_active']
    list_filter = ['is_system', 'is_active']
    search_fields = ['name', 'code']
    inlines = [RoleScreenPermissionInline]


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'module', 'order', 'is_active']
    list_filter = ['module', 'is_active']
    search_fields = ['name', 'code', 'module']
    ordering = ['module', 'order']


@admin.register(RoleScreenPermission)
class RoleScreenPermissionAdmin(admin.ModelAdmin):
    list_display = ['role', 'screen', 'grant_type', *_LEVEL_FIELDS]
    list_filter = ['grant_type', 'role', 'screen__module']
    autocomplete_fields = ['role', 'screen']


@admin.register(UserScreenPermission)
class UserScreenPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'screen', 'grant_type', *_LEVEL_FIELDS]
    list_filter = ['grant_type', 'screen__module']
    autocomplete_fields = ['user', 'screen']


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'granted_by', 'granted_at', 'valid_until']
    list_filter = ['role']
    autocomplete_fields = ['user', 'role', 'granted_by']


@admin.register(UserBranch)
class UserBranchAdmin(admin.ModelAdmin):
    list_display = ['user', 'branch', 'is_default', 'granted_at']
    list_filter = ['branch', 'is_default']
    autocomplete_fields = ['user']


@admin.register(UserWarehouse)
class UserWarehouseAdmin(admin.ModelAdmin):
    list_display = ['user', 'warehouse', 'can_receive', 'can_issue', 'can_count', 'can_transfer']
    list_filter = ['warehouse']
    autocomplete_fields = ['user']


@admin.register(UserAccountTypeScope)
class UserAccountTypeScopeAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_type', 'can_view', 'can_transact']
    list_filter = ['account_type']
    autocomplete_fields = ['user']
