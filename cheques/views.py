from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.exceptions import AccountingError
from common.permissions import screen_permission_required

from .forms import ChequeForm
from .models import Cheque


@screen_permission_required('cheques.cheque', 'view')
def cheque_list(request):
    cheques = Cheque.objects.select_related('customer', 'supplier').all()
    cheque_type = request.GET.get('type')
    status = request.GET.get('status')
    if cheque_type:
        cheques = cheques.filter(cheque_type=cheque_type)
    if status:
        cheques = cheques.filter(status=status)
    paginator = Paginator(cheques, 25)
    page = request.GET.get('page')
    cheques_page = paginator.get_page(page)
    return render(request, 'cheques/cheque_list.html', {'cheques': cheques_page})


@screen_permission_required('cheques.cheque', 'add')
def cheque_create(request):
    if request.method == 'POST':
        form = ChequeForm(request.POST)
        if form.is_valid():
            cheque = form.save(commit=False)
            cheque.created_by = request.user
            cheque.save()
            messages.success(request, 'تم إنشاء الشيك بنجاح')
            if cheque.cheque_type == 'issued':
                try:
                    cheque.post_issuance(request.user)
                    messages.success(request, 'تم ترحيل إصدار الشيك للاستاذ العام')
                except AccountingError as e:
                    messages.warning(request, f'تم حفظ الشيك ولكن لم يُرحل محاسبياً: {e}')
                except Exception as e:
                    messages.warning(request, f'تم حفظ الشيك ولكن حدث خطأ أثناء الترحيل المحاسبي: {e}')
            return redirect('cheques:cheque_detail', pk=cheque.pk)
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f'{form.fields[field].label if field in form.fields else field}: {err}')
    else:
        form = ChequeForm()
    return render(request, 'cheques/cheque_form.html', {'form': form})


@screen_permission_required('cheques.cheque', 'view')
def cheque_detail(request, pk):
    cheque = get_object_or_404(Cheque, pk=pk)
    return render(request, 'cheques/cheque_detail.html', {'cheque': cheque})


@require_POST
@screen_permission_required('cheques.cheque', 'edit')
def cheque_update_status(request, pk):
    cheque = get_object_or_404(Cheque, pk=pk)
    new_status = request.POST.get('status')
    valid_statuses = {choice[0] for choice in Cheque.STATUS_CHOICES}
    if new_status and new_status in valid_statuses:
        old_status = cheque.status
        cheque.status = new_status
        cheque.save(update_fields=['status'])
        try:
            if new_status in ('cleared', 'deposited'):
                cheque.post_clearing(request.user)
            elif new_status in ('bounced', 'cancelled'):
                cheque.reverse_gl(request.user)
            if new_status != old_status:
                messages.success(request, f'تم تحديث حالة الشيك إلى: {cheque.get_status_display()}')
        except AccountingError as e:
            messages.warning(request, f'تم تحديث الحالة ولكن لم يُرحل المحاسبة: {e}')
        except Exception as e:
            messages.warning(request, f'تم تحديث الحالة ولكن حدث خطأ أثناء الترحيل المحاسبي: {e}')
    elif new_status:
        messages.error(request, 'حالة غير صالحة')
    return redirect('cheques:cheque_detail', pk=pk)


@require_POST
@screen_permission_required('cheques.cheque', 'delete')
def cheque_delete(request, pk):
    cheque = get_object_or_404(Cheque, pk=pk)
    if cheque.status in ('cleared', 'cancelled'):
        messages.error(request, 'لا يمكن حذف شيك تم محصولته أو إلغائه')
        return redirect('cheques:cheque_detail', pk=pk)
    if cheque.journal_entry_id:
        try:
            cheque.reverse_gl(request.user)
        except Exception:
            pass
    cheque.delete()
    messages.success(request, 'تم حذف الشيك بنجاح')
    return redirect('cheques:cheque_list')


@screen_permission_required('cheques.cheque', 'view')
def cheque_dashboard(request):
    from datetime import date
    from decimal import Decimal

    today = date.today()

    received_pending = Cheque.objects.filter(cheque_type='received', status__in=['pending', 'deposited']).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    issued_pending = Cheque.objects.filter(cheque_type='issued', status='pending').aggregate(total=Sum('amount'))[
        'total'
    ] or Decimal('0')
    overdue = Cheque.objects.filter(cheque_type='received', status='pending', due_date__lt=today)
    total_overdue = overdue.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    recent_cheques = Cheque.objects.select_related('customer', 'supplier').all()[:10]

    return render(
        request,
        'cheques/cheque_dashboard.html',
        {
            'received_pending': received_pending,
            'issued_pending': issued_pending,
            'total_overdue': total_overdue,
            'overdue_count': overdue.count(),
            'recent_cheques': recent_cheques,
            'today': today,
        },
    )
