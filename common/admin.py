from django.contrib import admin

from .models import SequenceNumber


@admin.register(SequenceNumber)
class SequenceNumberAdmin(admin.ModelAdmin):
    list_display = ('sequence_type', 'prefix', 'last_number', 'year')
    list_filter = ('sequence_type', 'year')
    search_fields = ('sequence_type',)
