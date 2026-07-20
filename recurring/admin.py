from django.contrib import admin

from .models import RecurringJournal, RecurringJournalLine, RecurringJournalLog


class RecurringJournalLineInline(admin.TabularInline):
    model = RecurringJournalLine
    extra = 2


@admin.register(RecurringJournal)
class RecurringJournalAdmin(admin.ModelAdmin):
    list_display = ['name', 'frequency', 'next_due_date', 'status', 'total_debit', 'total_credit']
    list_filter = ['status', 'frequency']
    inlines = [RecurringJournalLineInline]


@admin.register(RecurringJournalLog)
class RecurringJournalLogAdmin(admin.ModelAdmin):
    list_display = ['journal', 'executed_date', 'journal_entry']
