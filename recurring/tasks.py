import logging
from celery import shared_task
from django.utils import timezone
from datetime import date, timedelta

logger = logging.getLogger('accounting')


@shared_task(name='recurring.execute_due_journals')
def execute_due_journals():
    from .models import RecurringJournal, RecurringJournalLog
    from accounts.models import Account, JournalEntry, JournalEntryLine
    from common.accounting_service import JournalEntryService
    from django.db import transaction

    today = date.today()
    due_journals = RecurringJournal.objects.filter(
        status='active',
        next_due_date__lte=today,
    ).prefetch_related('lines')

    executed = 0
    for rj in due_journals:
        try:
            with transaction.atomic():
                entry_lines = []
                for line in rj.lines.all():
                    entry_lines.append({
                        'account': line.account,
                        'debit': line.debit,
                        'credit': line.credit,
                        'description': line.description,
                    })

                if not entry_lines:
                    continue

                from django.contrib.auth.models import User
                admin_user = User.objects.filter(is_superuser=True).first()

                entry = JournalEntryService.create_entry(
                    entry_type=rj.journal_type or 'general',
                    date=today,
                    description=rj.description or rj.name,
                    reference=rj.reference or f'دوري: {rj.name}',
                    lines=entry_lines,
                    created_by=admin_user,
                )

                RecurringJournalLog.objects.create(
                    journal=rj, executed_date=today, journal_entry=entry,
                )

                if rj.frequency == 'daily':
                    rj.next_due_date += timedelta(days=1)
                elif rj.frequency == 'weekly':
                    rj.next_due_date += timedelta(weeks=1)
                elif rj.frequency == 'monthly':
                    month = rj.next_due_date.month + 1
                    year = rj.next_due_date.year
                    if month > 12:
                        month = 1
                        year += 1
                    rj.next_due_date = rj.next_due_date.replace(year=year, month=month, day=min(rj.day_of_month, 28))
                elif rj.frequency == 'quarterly':
                    month = rj.next_due_date.month + 3
                    year = rj.next_due_date.year
                    while month > 12:
                        month -= 12
                        year += 1
                    rj.next_due_date = rj.next_due_date.replace(year=year, month=month, day=min(rj.day_of_month, 28))
                elif rj.frequency == 'yearly':
                    rj.next_due_date = rj.next_due_date.replace(year=rj.next_due_date.year + 1)
                rj.save(update_fields=['next_due_date'])
                executed += 1
        except Exception as e:
            logger.error('Failed to execute recurring journal %s: %s', rj.pk, e)

    return f'Executed {executed} recurring journals'
