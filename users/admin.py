from django.contrib.auth.models import User, Group
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_superuser', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']


admin.site.unregister(Group)
