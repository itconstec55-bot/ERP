import logging
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.excel_utils import export_to_excel, import_from_excel
from common.permissions import can_account_type_operation, screen_permission_required, visible_account_type_ids
from common.utils import parse_date_range

from .forms import AccountForm, JournalEntryForm, JournalEntryLineFormSet
from .models import Account, AccountType, JournalEntry, JournalEntryLine

logger = logging.getLogger('accounting')


@screen_permission_required('accounts.account', 'view')
def account_list(request):
    accounts = Account.objects.select_related('account_type', 'parent').filter(is_active=True)
    allowed_types = visible_account_type_ids(request.user)
    if allowed_types is not None:
        accounts = accounts.filter(account_type_id__in=allowed_types)
    account_type = request.GET.get('type')
    if account_type:
        accounts = accounts.filter(account_type__account_type=account_type)
    paginator = Paginator(accounts, 30)
    page = request.GET.get('page')
    accounts_page = paginator.get_page(page)
    return render(request, 'accounts/account_list.html', {'accounts': accounts_page})


@screen_permission_required('accounts.account', 'add')
def account_create(request):
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            if (
                not can_account_type_operation(request.user, account.account_type_id, 'transact')
                and visible_account_type_ids(request.user) is not None
            ):
                messages.error(request, 'ليس لديك صلاحية إنشاء حسابات في هذه الفئة')
                return render(request, 'accounts/account_form.html', {'form': form})
            account.save()
            messages.success(request, 'تم إنشاء الحساب بنجاح')
            return redirect('accounts:account_list')
    else:
        form = AccountForm()
    return render(request, 'accounts/account_form.html', {'form': form})


@screen_permission_required('accounts.account', 'view')
def account_detail(request, pk):
    account = get_object_or_404(Account, pk=pk)
    allowed_types = visible_account_type_ids(request.user)
    if allowed_types is not None and str(account.account_type_id) not in allowed_types:
        messages.error(request, 'ليس لديك صلاحية على هذه الفئة من الحسابات')
        return redirect('accounts:account_list')
    entries = JournalEntryLine.objects.filter(account=account, journal_entry__is_posted=True).select_related(
        'journal_entry'
    )
    return render(request, 'accounts/account_detail.html', {'account': account, 'entries': entries})


@screen_permission_required('accounts.account', 'edit')
def account_edit(request, pk):
    account = get_object_or_404(Account, pk=pk)
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل الحساب بنجاح')
            return redirect('accounts:account_detail', pk=pk)
    else:
        form = AccountForm(instance=account)
    return render(request, 'accounts/account_form.html', {'form': form, 'account': account})


@screen_permission_required('accounts.account', 'view')
def account_statement(request, pk):
    account = get_object_or_404(Account, pk=pk)
    date_from, date_to = parse_date_range(request)

    lines = (
        JournalEntryLine.objects.filter(account=account, journal_entry__is_posted=True)
        .select_related('journal_entry')
        .order_by('journal_entry__date', 'journal_entry__entry_number')
    )

    if date_from:
        lines = lines.filter(journal_entry__date__gte=date_from)
    if date_to:
        lines = lines.filter(journal_entry__date__lte=date_to)

    # الرصيد الافتتاحي: مجموع ما قبل النطاق (على مستوى DB)
    opening_balance = account.opening_balance
    if date_from:
        pre_sum = (
            JournalEntryLine.objects.filter(
                account=account, journal_entry__is_posted=True, journal_entry__date__lt=date_from
            ).aggregate(s=Sum(F('debit') - F('credit')))['s']
            or 0
        )
        opening_balance += pre_sum

    # إجماليات ورقام التوازن على مستوى DB (بدون تحميل كل السجلات)
    totals = lines.aggregate(total_debit=Sum('debit'), total_credit=Sum('credit'), net=Sum(F('debit') - F('credit')))
    total_debit = totals['total_debit'] or 0
    total_credit = totals['total_credit'] or 0
    closing_balance = opening_balance + (totals['net'] or 0)

    # تقييد على مستوى DB (LIMIT/OFFSET) — لا نحمّل كل السطور في الذاكرة
    paginator = Paginator(lines, 50)
    page = request.GET.get('page')
    statement_page = paginator.get_page(page)

    start = (statement_page.number - 1) * paginator.per_page
    pre_page_sum = lines[:start].aggregate(s=Sum(F('debit') - F('credit')))['s'] or 0
    running_balance = opening_balance + pre_page_sum

    statement_data = []
    for line in statement_page:
        running_balance += line.debit - line.credit
        statement_data.append(
            {
                'date': line.journal_entry.date,
                'entry_number': line.journal_entry.entry_number,
                'description': line.description or line.journal_entry.description,
                'debit': line.debit,
                'credit': line.credit,
                'balance': running_balance,
            }
        )

    # استبدال عناصر الصفحة بالقاموس المحسوب (مع الحفاظ على واجهة الترقيم)
    statement_page.object_list = statement_data

    return render(
        request,
        'accounts/account_statement.html',
        {
            'account': account,
            'statement': statement_page,
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'date_from': date_from or '',
            'date_to': date_to or '',
        },
    )


@screen_permission_required('accounts.journalentry', 'view')
def journal_list(request):
    entries = JournalEntry.objects.select_related('created_by').all()
    entry_type = request.GET.get('type')
    date_from, date_to = parse_date_range(request)
    if entry_type:
        entries = entries.filter(entry_type=entry_type)
    if date_from:
        entries = entries.filter(date__gte=date_from)
    if date_to:
        entries = entries.filter(date__lte=date_to)
    entries = entries.order_by('-date', '-entry_number')
    paginator = Paginator(entries, 25)
    page = request.GET.get('page')
    entries_page = paginator.get_page(page)
    return render(request, 'accounts/journal_list.html', {'entries': entries_page})


@screen_permission_required('accounts.journalentry', 'add')
def journal_create(request):
    if request.method == 'POST':
        form = JournalEntryForm(request.POST)
        formset = JournalEntryLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                entry = form.save(commit=False)
                entry.created_by = request.user
                if not entry.entry_number:
                    from common.models import SequenceNumber

                    entry.entry_number = SequenceNumber.get_next_number('journal_entry')
                entry.save()
                formset.instance = entry
                formset.save()
                entry.calculate_totals()
            messages.success(request, 'تم إنشاء القيد بنجاح')
            return redirect('accounts:journal_detail', pk=entry.pk)
    else:
        form = JournalEntryForm()
        formset = JournalEntryLineFormSet()
    return render(request, 'accounts/journal_form.html', {'form': form, 'formset': formset})


@screen_permission_required('accounts.journalentry', 'view')
def journal_detail(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk)
    lines = entry.lines.select_related('account').all()
    return render(request, 'accounts/journal_detail.html', {'entry': entry, 'lines': lines})


@screen_permission_required('accounts.journalentry', 'edit')
def journal_edit(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk)
    if entry.is_posted:
        messages.error(request, 'لا يمكن تعديل قيد مرحل')
        return redirect('accounts:journal_detail', pk=pk)
    if request.method == 'POST':
        form = JournalEntryForm(request.POST, instance=entry)
        formset = JournalEntryLineFormSet(request.POST, instance=entry)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                entry = form.save()
                formset.save()
                entry.calculate_totals()
            messages.success(request, 'تم تعديل القيد بنجاح')
            return redirect('accounts:journal_detail', pk=pk)
    else:
        form = JournalEntryForm(instance=entry)
        formset = JournalEntryLineFormSet(instance=entry)
    return render(request, 'accounts/journal_form.html', {'form': form, 'formset': formset, 'entry': entry})


@require_POST
@screen_permission_required('accounts.journalentry', 'delete')
def journal_delete(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk)
    if entry.is_posted:
        messages.error(request, 'لا يمكن حذف قيد مرحل — ألغِ الترحيل أولاً')
    else:
        entry.delete()
        messages.success(request, 'تم حذف القيد بنجاح')
    return redirect('accounts:journal_list')


@require_POST
@screen_permission_required('accounts.journalentry', 'edit')
def journal_post(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk)
    try:
        entry.post()
        from audit.models import log_action

        log_action(
            request.user,
            'post',
            'accounts.journalentry',
            object_id=entry.pk,
            object_repr=str(entry)[:200],
            request=request,
        )
        messages.success(request, 'تم ترحيل القيد بنجاح')
    except ValueError as e:
        from audit.models import log_action

        log_action(
            request.user,
            'post',
            'accounts.journalentry',
            object_id=entry.pk,
            object_repr=str(entry)[:200],
            changes={'error': str(e)},
            request=request,
        )
        messages.error(request, 'لا يمكن ترحيل القيد - تأكد من صحة البيانات')
        logger.exception('Failed to post journal entry %s', pk)
    return redirect('accounts:journal_detail', pk=pk)


@screen_permission_required('accounts.journalentry', 'view')
def trial_balance(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    accounts = Account.objects.filter(is_active=True).select_related('account_type')

    total_debit = 0
    total_credit = 0

    if date_from or date_to:
        from common.utils import parse_date

        from .models import JournalEntryLine

        df = parse_date(date_from) if date_from else None
        dt = parse_date(date_to) if date_to else None
        entry_lines = JournalEntryLine.objects.filter(journal_entry__is_posted=True)
        if df:
            entry_lines = entry_lines.filter(journal_entry__date__gte=df)
        if dt:
            entry_lines = entry_lines.filter(journal_entry__date__lte=dt)
        balances = {}
        for acc_id, acc_type in accounts.values_list('pk', 'account_type__account_type'):
            balances[acc_id] = {'type': acc_type, 'debit': 0, 'credit': 0}
        for line in entry_lines.select_related('account', 'account__account_type'):
            acc = line.account
            if acc.pk in balances:
                if balances[acc.pk]['type'] in ['asset', 'expense']:
                    balances[acc.pk]['debit'] += line.debit
                    balances[acc.pk]['credit'] += line.credit
                else:
                    balances[acc.pk]['debit'] += line.credit
                    balances[acc.pk]['credit'] += line.debit
        for b in balances.values():
            net = b['debit'] - b['credit']
            if net > 0:
                total_debit += net
            else:
                total_credit += abs(net)
    else:
        for account in accounts:
            if account.current_balance > 0:
                if account.account_type.account_type in ['asset', 'expense']:
                    total_debit += account.current_balance
                else:
                    total_credit += account.current_balance
            elif account.current_balance < 0:
                if account.account_type.account_type in ['asset', 'expense']:
                    total_credit += abs(account.current_balance)
                else:
                    total_debit += abs(account.current_balance)

    return render(
        request,
        'accounts/trial_balance.html',
        {
            'accounts': accounts,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'date_from': date_from or '',
            'date_to': date_to or '',
        },
    )


@screen_permission_required('accounts.account', 'view')
def chart_of_accounts(request):
    account_types = AccountType.objects.prefetch_related('accounts').all()
    return render(request, 'accounts/chart_of_accounts.html', {'account_types': account_types})


@screen_permission_required('accounts.account', 'export')
def export_accounts(request):
    accounts = Account.objects.select_related('account_type', 'parent').all()
    return export_to_excel(
        accounts,
        [
            {'field': 'code', 'header': 'الكود', 'width': 12},
            {'field': 'name', 'header': 'اسم الحساب', 'width': 30},
            {'field': lambda a: a.account_type.name, 'header': 'نوع الحساب', 'width': 20},
            {'field': lambda a: a.parent.code if a.parent else '', 'header': 'الحساب الأب', 'width': 12},
            {'field': 'current_balance', 'header': 'الرصيد الحالي', 'width': 15, 'format': '#,##0.00'},
            {'field': 'opening_balance', 'header': 'الرصيد الافتتاحي', 'width': 15, 'format': '#,##0.00'},
            {'field': lambda a: 'نشط' if a.is_active else 'غير نشط', 'header': 'الحالة', 'width': 10},
        ],
        filename='accounts',
    )


@screen_permission_required('accounts.account', 'add')
def import_accounts(request):
    if request.method != 'POST':
        return redirect('accounts:account_list')
    file = request.FILES.get('excel_file')
    if not file:
        messages.error(request, 'يرجى اختيار ملف Excel')
        return redirect('accounts:account_list')
    try:
        rows = import_from_excel(
            file,
            [
                {'field': 'code', 'header': 'الكود'},
                {'field': 'name', 'header': 'اسم الحساب'},
                {'field': 'account_type_name', 'header': 'نوع الحساب'},
                {'field': 'current_balance', 'header': 'الرصيد الحالي', 'type': 'decimal'},
            ],
        )
        type_lookup = {t.name: t for t in AccountType.objects.all()}
        created = 0
        for row in rows:
            if not row.get('code') or not row.get('name'):
                continue
            type_name = row.get('account_type_name', '')
            account_type = type_lookup.get(type_name)
            if not account_type:
                continue
            Account.objects.get_or_create(
                code=row['code'],
                defaults={
                    'name': row['name'],
                    'account_type': account_type,
                    'current_balance': row.get('current_balance') or 0,
                },
            )
            created += 1
        messages.success(request, f'تم استيراد {created} حساب بنجاح')
    except Exception:
        messages.error(request, 'حدث خطأ أثناء استيراد الحسابات. تأكد من صحة بيانات الملف وحاول مرة أخرى.')
        logger.exception('Import accounts failed')
    return redirect('accounts:account_list')


@screen_permission_required('accounts.journalentry', 'export')
def export_journal(request):
    entries = JournalEntry.objects.all()
    return export_to_excel(
        entries,
        [
            {'field': 'entry_number', 'header': 'رقم القيد', 'width': 12},
            {'field': 'date', 'header': 'التاريخ', 'width': 12},
            {'field': lambda e: e.get_entry_type_display(), 'header': 'النوع', 'width': 15},
            {'field': 'description', 'header': 'البيان', 'width': 30},
            {'field': 'total_debit', 'header': 'مدين', 'width': 15, 'format': '#,##0.00'},
            {'field': 'total_credit', 'header': 'دائن', 'width': 15, 'format': '#,##0.00'},
            {'field': lambda e: 'مرحل' if e.is_posted else 'مسودة', 'header': 'الحالة', 'width': 10},
        ],
        filename='journal_entries',
    )


@screen_permission_required('accounts.journalentry', 'edit')
def fiscal_year_close(request):
    if request.method == 'POST':
        close_year = request.POST.get('year')
        if close_year:
            try:
                close_year = int(close_year)
            except (ValueError, TypeError):
                messages.error(request, 'السنة المالية غير صحيحة')
                return redirect('accounts:fiscal_year_close')

            with transaction.atomic():
                revenue_accounts = Account.objects.filter(
                    account_type__account_type__in=['revenue', 'expense'], is_active=True
                ).select_related('account_type')
                total_revenue = Decimal('0')
                total_expense = Decimal('0')
                for acc in revenue_accounts:
                    if acc.account_type.account_type == 'revenue':
                        total_revenue += acc.current_balance
                    else:
                        total_expense += acc.current_balance

                profit = total_revenue - total_expense

                equity_account = Account.objects.filter(code='5100').first()
                if not equity_account:
                    messages.error(request, 'حساب حقوق الملكية (5100) غير موجود')
                    return redirect('accounts:fiscal_year_close')

                equity_account.current_balance += profit
                equity_account.save(update_fields=['current_balance'])

                for acc in revenue_accounts:
                    acc.opening_balance = acc.current_balance
                    acc.current_balance = Decimal('0')
                    acc.save(update_fields=['opening_balance', 'current_balance'])

            messages.success(request, f'تم إغلاق السنة المالية {close_year} بنجاح. صافي الربح: {profit:,.2f} ج.م')
            return redirect('accounts:account_list')

    accounts = Account.objects.filter(
        account_type__account_type__in=['revenue', 'expense'], is_active=True
    ).select_related('account_type')
    total_revenue = Decimal('0')
    total_expense = Decimal('0')
    for acc in accounts:
        if acc.account_type.account_type == 'revenue':
            total_revenue += acc.current_balance
        else:
            total_expense += acc.current_balance

    return render(
        request,
        'accounts/fiscal_year_close.html',
        {
            'accounts': accounts,
            'total_revenue': total_revenue,
            'total_expense': total_expense,
            'net_profit': total_revenue - total_expense,
        },
    )
