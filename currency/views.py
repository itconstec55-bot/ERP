from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from common.permissions import screen_permission_required

from .forms import CurrencyForm
from .models import Currency, ExchangeRateHistory


@screen_permission_required('currency.currency', 'view')
def currency_list(request):
    currencies = Currency.objects.filter(is_active=True)
    return render(request, 'currency/currency_list.html', {'currencies': currencies})


@screen_permission_required('currency.currency', 'add')
def currency_create(request):
    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء العملة بنجاح')
            return redirect('currency:currency_list')
        for field, errs in form.errors.items():
            for err in errs:
                label = form.fields[field].label if field in form.fields else field
                messages.error(request, f'{label}: {err}')
    else:
        form = CurrencyForm()
    return render(request, 'currency/currency_form.html', {'form': form})


@screen_permission_required('currency.currency', 'edit')
def currency_edit(request, pk):
    currency = get_object_or_404(Currency, pk=pk)
    if request.method == 'POST':
        form = CurrencyForm(request.POST, instance=currency)
        if form.is_valid():
            old_rate = currency.exchange_rate_to_egp
            currency = form.save()
            if old_rate != currency.exchange_rate_to_egp:
                ExchangeRateHistory.objects.create(
                    currency=currency, rate=currency.exchange_rate_to_egp, date=date.today()
                )
            messages.success(request, 'تم تعديل العملة بنجاح')
            return redirect('currency:currency_list')
        for field, errs in form.errors.items():
            for err in errs:
                label = form.fields[field].label if field in form.fields else field
                messages.error(request, f'{label}: {err}')
    else:
        form = CurrencyForm(instance=currency)
    return render(request, 'currency/currency_form.html', {'form': form, 'currency': currency})


@screen_permission_required('currency.currency', 'view')
def exchange_rate_history(request):
    history = ExchangeRateHistory.objects.select_related('currency').all()[:100]
    return render(request, 'currency/exchange_rate_history.html', {'history': history})
