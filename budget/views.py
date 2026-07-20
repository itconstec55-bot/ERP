from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.permissions import screen_permission_required

from .forms import BudgetForm, CostCenterForm
from .models import Budget, CostCenter


@screen_permission_required('budget.budget', 'view')
def cost_center_list(request):
    centers = CostCenter.objects.filter(is_active=True)
    return render(request, 'budget/cost_center_list.html', {'centers': centers})


@screen_permission_required('budget.budget', 'view')
def cost_center_detail(request, pk):
    center = get_object_or_404(CostCenter, pk=pk)
    budgets = Budget.objects.filter(cost_center=center)
    return render(request, 'budget/cost_center_detail.html', {'center': center, 'budgets': budgets})


@screen_permission_required('budget.budget', 'add')
def cost_center_create(request):
    if request.method == 'POST':
        form = CostCenterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء مركز التكلفة بنجاح')
            return redirect('budget:cost_center_list')
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f'{form.fields[field].label if field in form.fields else field}: {err}')
        parents = CostCenter.objects.filter(is_active=True)
        return render(request, 'budget/cost_center_form.html', {'parents': parents, 'form': form})
    parents = CostCenter.objects.filter(is_active=True)
    return render(request, 'budget/cost_center_form.html', {'parents': parents, 'form': CostCenterForm()})


@screen_permission_required('budget.budget', 'edit')
def cost_center_edit(request, pk):
    center = get_object_or_404(CostCenter, pk=pk)
    if request.method == 'POST':
        form = CostCenterForm(request.POST, instance=center)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل مركز التكلفة بنجاح')
            return redirect('budget:cost_center_detail', pk=pk)
    else:
        form = CostCenterForm(instance=center)
    parents = CostCenter.objects.filter(is_active=True).exclude(pk=pk)
    return render(request, 'budget/cost_center_form.html', {'parents': parents, 'form': form, 'center': center})


@require_POST
@screen_permission_required('budget.budget', 'delete')
def cost_center_delete(request, pk):
    center = get_object_or_404(CostCenter, pk=pk)
    if Budget.objects.filter(cost_center=center).exists():
        messages.error(request, 'لا يمكن حذف مركز تكلفة مرتبط بموازنة')
    else:
        center.delete()
        messages.success(request, 'تم حذف مركز التكلفة بنجاح')
    return redirect('budget:cost_center_list')


@screen_permission_required('budget.budget', 'view')
def budget_list(request):
    budgets = Budget.objects.select_related('account', 'cost_center').all()
    year = request.GET.get('year', '')
    if year:
        budgets = budgets.filter(year=year)
    total_budgeted = budgets.aggregate(t=Sum('budgeted_amount'))['t'] or 0
    total_actual = budgets.aggregate(t=Sum('actual_amount'))['t'] or 0
    return render(
        request,
        'budget/budget_list.html',
        {'budgets': budgets, 'total_budgeted': total_budgeted, 'total_actual': total_actual},
    )


@screen_permission_required('budget.budget', 'add')
def budget_create(request):
    from accounts.models import Account

    accounts = Account.objects.filter(is_active=True)
    cost_centers = CostCenter.objects.filter(is_active=True)

    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء الموازنة بنجاح')
            return redirect('budget:budget_list')
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f'{form.fields[field].label if field in form.fields else field}: {err}')
        return render(
            request, 'budget/budget_form.html', {'accounts': accounts, 'cost_centers': cost_centers, 'form': form}
        )

    return render(
        request, 'budget/budget_form.html', {'accounts': accounts, 'cost_centers': cost_centers, 'form': BudgetForm()}
    )


@screen_permission_required('budget.budget', 'view')
def budget_detail(request, pk):
    budget = get_object_or_404(Budget.objects.select_related('account', 'cost_center'), pk=pk)
    return render(request, 'budget/budget_detail.html', {'budget': budget})


@screen_permission_required('budget.budget', 'edit')
def budget_edit(request, pk):
    from accounts.models import Account

    budget = get_object_or_404(Budget, pk=pk)
    accounts = Account.objects.filter(is_active=True)
    cost_centers = CostCenter.objects.filter(is_active=True)

    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل الموازنة بنجاح')
            return redirect('budget:budget_detail', pk=pk)
    else:
        form = BudgetForm(instance=budget)
    return render(
        request,
        'budget/budget_form.html',
        {'accounts': accounts, 'cost_centers': cost_centers, 'form': form, 'budget': budget},
    )


@require_POST
@screen_permission_required('budget.budget', 'delete')
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk)
    budget.delete()
    messages.success(request, 'تم حذف الموازنة بنجاح')
    return redirect('budget:budget_list')


@screen_permission_required('budget.budget', 'view')
def budget_report(request):
    """تقرير الموازنة الشامل — يقارن الفعلي بالمخطط لكل الحسابات."""
    from decimal import Decimal

    from django.db.models import Sum

    from accounts.models import JournalEntryLine

    year = request.GET.get('year', '')
    if not year:
        from django.utils import timezone

        year = timezone.now().year
    else:
        year = int(year)

    budgets = Budget.objects.select_related('account', 'cost_center').filter(year=year)

    report_data = []
    for budget in budgets:
        actual = JournalEntryLine.objects.filter(account=budget.account, journal_entry__date__year=year)
        if budget.month:
            actual = actual.filter(journal_entry__date__month=budget.month)
        if budget.cost_center:
            actual = actual.filter(journal_entry__cost_center=budget.cost_center)

        debit_total = actual.aggregate(t=Sum('debit'))['t'] or Decimal('0')
        credit_total = actual.aggregate(t=Sum('credit'))['t'] or Decimal('0')

        if budget.account.account_type and budget.account.account_type.code.startswith(('4', '5')):
            actual_val = credit_total - debit_total
        else:
            actual_val = debit_total - credit_total

        budget.actual_amount = abs(actual_val)
        budget.save(update_fields=['actual_amount'])

        report_data.append(budget)

    total_budgeted = sum(b.budgeted_amount for b in report_data)
    total_actual = sum(b.actual_amount for b in report_data)
    exec_pct = round((total_actual / total_budgeted * 100), 1) if total_budgeted > 0 else 0

    for b in report_data:
        if b.budgeted_amount > 0:
            b.pct = round((b.actual_amount / b.budgeted_amount * 100), 1)
        else:
            b.pct = 0

    return render(
        request,
        'budget/budget_report.html',
        {
            'report_data': report_data,
            'year': year,
            'total_budgeted': total_budgeted,
            'total_actual': total_actual,
            'exec_pct': exec_pct,
        },
    )
