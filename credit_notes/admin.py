from django.contrib import admin

from .models import CreditNote


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ['note_number', 'note_type', 'date', 'total_amount', 'is_posted']
    list_filter = ['note_type', 'is_posted']
