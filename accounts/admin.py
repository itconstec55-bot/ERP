from django.contrib import admin
from .models import AccountType, Account, JournalEntry, JournalEntryLine


class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name')


class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'parent', 'current_balance', 'is_active')
    list_filter = ('account_type', 'is_active', 'is_bank', 'is_safe', 'tax_account')
    search_fields = ('code', 'name')
    readonly_fields = ('current_balance', 'created_at', 'updated_at')


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 1
    fields = ('account', 'debit', 'credit', 'description')


class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('entry_number', 'entry_type', 'date', 'description', 'total_debit', 'total_credit', 'is_posted', 'is_reversed')
    list_filter = ('entry_type', 'is_posted', 'is_reversed', 'date')
    search_fields = ('entry_number', 'description')
    inlines = [JournalEntryLineInline]
    readonly_fields = ('total_debit', 'total_credit')

    def save_model(self, request, obj, form, change):
        if obj.is_posted:
            from django.contrib import messages
            messages.error(request, 'لا يمكن تعديل قيد مرحّل. قم بعكسه أولاً إن لزم.')
            return
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_posted:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_posted:
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.is_posted:
            return [f.name for f in self.model._meta.fields] + ['total_debit', 'total_credit']
        return self.readonly_fields

    def get_inline_instances(self, request, obj=None):
        if obj is not None and obj.is_posted:
            return []
        return super().get_inline_instances(request, obj)


admin.site.register(AccountType, AccountTypeAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(JournalEntry, JournalEntryAdmin)
admin.site.register(JournalEntryLine)
