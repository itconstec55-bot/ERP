from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import date, timedelta
from .models import RecurringJournal, RecurringJournalLine, RecurringJournalLog
from .forms import RecurringJournalForm
from accounts.models import Account, JournalEntry, JournalEntryLine


@login_required
def recurring_list(request):
    journals = RecurringJournal.objects.all()
    active = journals.filter(status='active').count()
    return render(request, 'recurring/recurring_list.html', {'journals': journals, 'active_count': active})


@login_required
def recurring_detail(request, pk):
    rj = get_object_or_404(RecurringJournal.objects.prefetch_related('lines__account', 'logs__journal_entry'), pk=pk)
    return render(request, 'recurring/recurring_detail.html', {'rj': rj})


@login_required
def recurring_create(request):
    accounts = Account.objects.filter(is_active=True)
    if request.method == 'POST':
        form = RecurringJournalForm(request.POST)
        if form.is_valid():
            rj = form.save(commit=False)
            rj.created_by = request.user
            rj.save()
            _save_lines(rj, request)
            messages.success(request, 'تم إنشاء القيد الدوري')
            return redirect('recurring:recurring_list')
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f'{form.fields[field].label if field in form.fields else field}: {err}')
        return render(request, 'recurring/recurring_form.html', {'accounts': accounts, 'form': form})
    return render(request, 'recurring/recurring_form.html', {'accounts': accounts, 'form': RecurringJournalForm()})


@login_required
def recurring_edit(request, pk):
    rj = get_object_or_404(RecurringJournal, pk=pk)
    accounts = Account.objects.filter(is_active=True)
    if request.method == 'POST':
        form = RecurringJournalForm(request.POST, instance=rj)
        if form.is_valid():
            rj = form.save()
            rj.lines.all().delete()
            _save_lines(rj, request)
            messages.success(request, 'تم تحديث القيد الدوري')
            return redirect('recurring:recurring_list')
        for field, errs in form.errors.items():
            for err in errs:
                label = form.fields[field].label if field in form.fields else field
                messages.error(request, f'{label}: {err}')
        existing_lines = rj.lines.all()
        return render(request, 'recurring/recurring_form.html', {
            'accounts': accounts, 'rj': rj, 'existing_lines': existing_lines, 'form': form,
        })
    existing_lines = rj.lines.all()
    return render(request, 'recurring/recurring_form.html', {
        'accounts': accounts, 'rj': rj, 'existing_lines': existing_lines, 'form': RecurringJournalForm(instance=rj),
    })


@require_POST
@login_required
def recurring_execute(request, pk):
    rj = get_object_or_404(RecurringJournal.objects.prefetch_related('lines'), pk=pk)
    if rj.status != 'active':
        messages.error(request, 'القيد الدوري غير نشط')
        return redirect('recurring:recurring_list')

    with transaction.atomic():
        from common.accounting_service import JournalEntryService
        entry_lines = []
        for line in rj.lines.all():
            entry_lines.append({
                'account': line.account,
                'debit': line.debit,
                'credit': line.credit,
                'description': line.description,
            })

        if not entry_lines:
            messages.error(request, 'لا توجد بنود في القيد الدوري')
            return redirect('recurring:recurring_list')

        entry = JournalEntryService.create_entry(
            entry_type=rj.journal_type or 'general',
            date=timezone.now().date(),
            description=rj.description or rj.name,
            reference=rj.reference or f'دوري: {rj.name}',
            lines=entry_lines,
            created_by=request.user,
        )

        RecurringJournalLog.objects.create(
            journal=rj, executed_date=timezone.now().date(), journal_entry=entry,
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

        messages.success(request, f'تم تنفيذ القيد "{rj.name}" وتم إنشاء قيد رقم {entry.entry_number}')
    return redirect('recurring:recurring_list')


@login_required
def recurring_toggle(request, pk):
    rj = get_object_or_404(RecurringJournal, pk=pk)
    if request.method == 'POST':
        rj.status = 'paused' if rj.status == 'active' else 'active'
        rj.save()
    return redirect('recurring:recurring_list')


@login_required
def recurring_delete(request, pk):
    rj = get_object_or_404(RecurringJournal, pk=pk)
    if request.method == 'POST':
        rj.delete()
        messages.success(request, 'تم حذف القيد الدوري')
    return redirect('recurring:recurring_list')


def _save_lines(rj, request):
    accounts = request.POST.getlist('line_account')
    descriptions = request.POST.getlist('line_description')
    debits = request.POST.getlist('line_debit')
    credits = request.POST.getlist('line_credit')
    from decimal import Decimal
    total_d = Decimal('0')
    total_c = Decimal('0')
    for i in range(len(accounts)):
        if accounts[i]:
            d = Decimal(debits[i]) if i < len(debits) and debits[i] else Decimal('0')
            c = Decimal(credits[i]) if i < len(credits) and credits[i] else Decimal('0')
            RecurringJournalLine.objects.create(
                journal=rj, account_id=accounts[i],
                description=descriptions[i] if i < len(descriptions) else '',
                debit=d, credit=c,
            )
            total_d += d
            total_c += c
    rj.total_debit = total_d
    rj.total_credit = total_c
    rj.save()
