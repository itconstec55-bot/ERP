from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from common.permissions import screen_permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone

from .models import (
    Contractor, Contract, ContractItem, InterimCertificate,
    CertificateItem, ContractorPayment
)
from .forms import (
    ContractorForm, ContractorFilterForm, ContractForm, ContractFilterForm,
    ContractItemFormSet, InterimCertificateForm, CertificateItemFormSet,
    ContractorPaymentForm
)


# ══════════════════════════════════════════════════════════════
# لوحة التحكم
# ══════════════════════════════════════════════════════════════

@screen_permission_required('contractors.contractor', 'view')
def dashboard(request):
    context = {
        'total_contractors': Contractor.objects.filter(is_active=True).count(),
        'active_contracts': Contract.objects.filter(status__in=['active', 'in_progress']).count(),
        'pending_certificates': InterimCertificate.objects.filter(status__in=['draft', 'submitted']).count(),
        'total_contracts_value': float(
            Contract.objects.filter(status__in=['active', 'in_progress']).aggregate(
                total=Sum('contract_amount')
            )['total'] or 0
        ),
        'total_certified': float(
            InterimCertificate.objects.filter(status__in=['approved', 'certified']).aggregate(
                total=Sum('net_amount')
            )['total'] or 0
        ),
        'total_payments': float(
            ContractorPayment.objects.filter(status='paid').aggregate(
                total=Sum('amount')
            )['total'] or 0
        ),
        'recent_contracts': Contract.objects.select_related('contractor')[:10],
        'recent_certificates': InterimCertificate.objects.select_related(
            'contract__contractor'
        )[:5],
    }
    return render(request, 'contractors/dashboard.html', context)


# ══════════════════════════════════════════════════════════════
# المقاولون
# ══════════════════════════════════════════════════════════════

@screen_permission_required('contractors.contractor', 'view')
def contractor_list(request):
    contractors = Contractor.objects.all()
    filter_form = ContractorFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('search'):
            s = filter_form.cleaned_data['search']
            contractors = contractors.filter(Q(name__icontains=s) | Q(code__icontains=s) | Q(phone__icontains=s))
        if filter_form.cleaned_data.get('status'):
            contractors = contractors.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('contractor_type'):
            contractors = contractors.filter(contractor_type=filter_form.cleaned_data['contractor_type'])
    paginator = Paginator(contractors, 25)
    page = request.GET.get('page')
    contractors_page = paginator.get_page(page)
    return render(request, 'contractors/contractor_list.html', {
        'contractors': contractors_page, 'filter_form': filter_form,
    })


@screen_permission_required('contractors.contractor', 'add')
def contractor_create(request):
    if request.method == 'POST':
        form = ContractorForm(request.POST)
        if form.is_valid():
            contractor = form.save()
            messages.success(request, f'تم إضافة المقاول {contractor.name} بنجاح')
            return redirect('contractors:contractor_detail', pk=contractor.pk)
    else:
        form = ContractorForm()
    return render(request, 'contractors/contractor_form.html', {
        'form': form, 'title': 'إضافة مقاول جديد',
    })


@screen_permission_required('contractors.contractor', 'view')
def contractor_detail(request, pk):
    contractor = get_object_or_404(Contractor, pk=pk)
    contracts = contractor.contracts.all()
    payments = ContractorPayment.objects.filter(contract__contractor=contractor)[:10]
    return render(request, 'contractors/contractor_detail.html', {
        'contractor': contractor, 'contracts': contracts, 'payments': payments,
    })


@screen_permission_required('contractors.contractor', 'edit')
def contractor_edit(request, pk):
    contractor = get_object_or_404(Contractor, pk=pk)
    if request.method == 'POST':
        form = ContractorForm(request.POST, instance=contractor)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات المقاول')
            return redirect('contractors:contractor_detail', pk=contractor.pk)
    else:
        form = ContractorForm(instance=contractor)
    return render(request, 'contractors/contractor_form.html', {
        'form': form, 'contractor': contractor, 'title': 'تعديل بيانات المقاول',
    })


# ══════════════════════════════════════════════════════════════
# العقود
# ══════════════════════════════════════════════════════════════

@screen_permission_required('contractors.contractor', 'view')
def contract_list(request):
    contracts = Contract.objects.select_related('contractor')
    filter_form = ContractFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            contracts = contracts.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('contractor'):
            contracts = contracts.filter(contractor=filter_form.cleaned_data['contractor'])
    paginator = Paginator(contracts, 25)
    page = request.GET.get('page')
    contracts_page = paginator.get_page(page)
    return render(request, 'contractors/contract_list.html', {
        'contracts': contracts_page, 'filter_form': filter_form,
    })


@screen_permission_required('contractors.contractor', 'add')
def contract_create(request):
    if request.method == 'POST':
        form = ContractForm(request.POST)
        formset = ContractItemFormSet(request.POST, prefix='items')
        if form.is_valid() and formset.is_valid():
            contract = form.save(commit=False)
            contract.created_by = request.user
            contract.save()
            formset.instance = contract
            formset.save()
            messages.success(request, f'تم إنشاء العقد {contract.contract_number} بنجاح')
            return redirect('contractors:contract_detail', pk=contract.pk)
    else:
        form = ContractForm()
        formset = ContractItemFormSet(prefix='items')
    return render(request, 'contractors/contract_form.html', {
        'form': form, 'formset': formset, 'title': 'عقد جديد',
    })


@screen_permission_required('contractors.contractor', 'view')
def contract_detail(request, pk):
    contract = get_object_or_404(
        Contract.objects.select_related('contractor'), pk=pk
    )
    items = contract.items.all()
    certificates = contract.certificates.all()
    payments = contract.payments.all()
    return render(request, 'contractors/contract_detail.html', {
        'contract': contract, 'items': items,
        'certificates': certificates, 'payments': payments,
    })


@screen_permission_required('contractors.contractor', 'edit')
def contract_edit(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    if request.method == 'POST':
        form = ContractForm(request.POST, instance=contract)
        formset = ContractItemFormSet(request.POST, instance=contract, prefix='items')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'تم تحديث العقد')
            return redirect('contractors:contract_detail', pk=contract.pk)
    else:
        form = ContractForm(instance=contract)
        formset = ContractItemFormSet(instance=contract, prefix='items')
    return render(request, 'contractors/contract_form.html', {
        'form': form, 'formset': formset, 'contract': contract, 'title': 'تعديل العقد',
    })


@screen_permission_required('contractors.contractor', 'edit')
def contract_approve(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    if request.method == 'POST':
        contract.status = 'active'
        contract.signing_date = timezone.now().date()
        contract.save(update_fields=['status', 'signing_date'])
        messages.success(request, f'تم تفعيل العقد {contract.contract_number}')
    return redirect('contractors:contract_detail', pk=contract.pk)


@screen_permission_required('contractors.contractor', 'edit')
def contract_close(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    if request.method == 'POST':
        contract.status = 'closed'
        contract.actual_end_date = timezone.now().date()
        contract.save(update_fields=['status', 'actual_end_date'])
        messages.success(request, f'تم إغلاق العقد {contract.contract_number}')
    return redirect('contractors:contract_detail', pk=contract.pk)


# ══════════════════════════════════════════════════════════════
# المستخلصات
# ══════════════════════════════════════════════════════════════

@screen_permission_required('contractors.contractor', 'view')
def certificate_list(request):
    certificates = InterimCertificate.objects.select_related('contract__contractor')
    status = request.GET.get('status', '')
    if status:
        certificates = certificates.filter(status=status)
    paginator = Paginator(certificates, 25)
    page = request.GET.get('page')
    certificates_page = paginator.get_page(page)
    return render(request, 'contractors/certificate_list.html', {
        'certificates': certificates_page, 'status': status,
    })


@screen_permission_required('contractors.contractor', 'add')
def certificate_create(request):
    if request.method == 'POST':
        form = InterimCertificateForm(request.POST)
        formset = CertificateItemFormSet(request.POST, prefix='cert_items')
        if form.is_valid() and formset.is_valid():
            cert = form.save(commit=False)
            cert.created_by = request.user
            cert.save()
            formset.instance = cert
            formset.save()
            cert.calculate_totals()
            messages.success(request, f'تم إنشاء المستخلص {cert.certificate_number}')
            return redirect('contractors:certificate_detail', pk=cert.pk)
    else:
        form = InterimCertificateForm()
        formset = CertificateItemFormSet(prefix='cert_items')
    return render(request, 'contractors/certificate_form.html', {
        'form': form, 'formset': formset, 'title': 'مستخلص جديد',
    })


@screen_permission_required('contractors.contractor', 'view')
def certificate_detail(request, pk):
    cert = get_object_or_404(
        InterimCertificate.objects.select_related('contract__contractor'), pk=pk
    )
    items = cert.items.select_related('contract_item').all()
    return render(request, 'contractors/certificate_detail.html', {
        'cert': cert, 'items': items,
    })


@screen_permission_required('contractors.contractor', 'edit')
def certificate_approve(request, pk):
    cert = get_object_or_404(InterimCertificate, pk=pk)
    if request.method == 'POST':
        cert.status = 'approved'
        cert.approval_date = timezone.now().date()
        cert.calculate_totals()
        cert.save(update_fields=['status', 'approval_date'])
        messages.success(request, f'تم اعتماد المستخلص {cert.certificate_number}')
    return redirect('contractors:certificate_detail', pk=pk)


@screen_permission_required('contractors.contractor', 'edit')
def certificate_post(request, pk):
    """ترحيل المستخلص إلى دفتر الأستاذ"""
    cert = get_object_or_404(InterimCertificate, pk=pk)
    if request.method == 'POST':
        try:
            cert.create_journal_entry()
            cert.status = 'certified'
            cert.save(update_fields=['status'])
            cert.contract.calculate_totals()
            messages.success(request, f'تم ترحيل المستخلص {cert.certificate_number} بنجاح')
        except Exception as e:
            messages.error(request, f'خطأ في الترحيل: {str(e)}')
    return redirect('contractors:certificate_detail', pk=pk)


# ══════════════════════════════════════════════════════════════
# المدفوعات
# ══════════════════════════════════════════════════════════════

@screen_permission_required('contractors.contractor', 'view')
def payment_list(request):
    payments = ContractorPayment.objects.select_related('contract__contractor', 'certificate')
    status = request.GET.get('status', '')
    if status:
        payments = payments.filter(status=status)
    paginator = Paginator(payments, 25)
    page = request.GET.get('page')
    payments_page = paginator.get_page(page)
    return render(request, 'contractors/payment_list.html', {
        'payments': payments_page, 'status': status,
    })


@screen_permission_required('contractors.contractor', 'add')
def payment_create(request):
    if request.method == 'POST':
        form = ContractorPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.created_by = request.user
            payment.save()
            messages.success(request, f'تم إنشاء الدفعة {payment.payment_number}')
            try:
                from notifications.utils import notify_contractor_payment_created
                notify_contractor_payment_created(payment)
            except Exception:
                pass
            return redirect('contractors:payment_detail', pk=payment.pk)
    else:
        form = ContractorPaymentForm()
        contract_pk = request.GET.get('contract', '')
        cert_pk = request.GET.get('certificate', '')
        if contract_pk:
            form.fields['contract'].initial = contract_pk
        if cert_pk:
            form.fields['certificate'].initial = cert_pk
    return render(request, 'contractors/payment_form.html', {
        'form': form, 'title': 'دفعة جديدة',
    })


@screen_permission_required('contractors.contractor', 'view')
def payment_detail(request, pk):
    payment = get_object_or_404(
        ContractorPayment.objects.select_related('contract__contractor', 'certificate'),
        pk=pk
    )
    return render(request, 'contractors/payment_detail.html', {
        'payment': payment,
    })


@screen_permission_required('contractors.contractor', 'edit')
def payment_post(request, pk):
    """ترحيل الدفعة إلى دفتر الأستاذ"""
    payment = get_object_or_404(ContractorPayment, pk=pk)
    if request.method == 'POST':
        try:
            payment.create_journal_entry()
            payment.status = 'paid'
            if payment.certificate:
                payment.certificate.paid_amount += payment.amount
                payment.certificate.status = 'paid'
                payment.certificate.save(update_fields=['paid_amount', 'status'])
            payment.save(update_fields=['status'])
            messages.success(request, f'تم ترحيل الدفعة {payment.payment_number} بنجاح')
            try:
                from notifications.utils import notify_contractor_payment_posted
                notify_contractor_payment_posted(payment)
            except Exception:
                pass
        except Exception as e:
            messages.error(request, f'خطأ في الترحيل: {str(e)}')
    return redirect('contractors:payment_detail', pk=pk)


# ══════════════════════════════════════════════════════════════
# API
# ══════════════════════════════════════════════════════════════

@screen_permission_required('contractors.contractor', 'view')
def api_contract_items(request, pk):
    """API: بنود العقد"""
    contract = get_object_or_404(Contract, pk=pk)
    items = list(contract.items.values('id', 'item_number', 'description', 'unit', 'quantity', 'unit_price', 'executed_quantity'))
    return JsonResponse({'items': items})


@screen_permission_required('contractors.contractor', 'view')
def api_contractor_stats(request, pk):
    """API: إحصائيات المقاول"""
    contractor = get_object_or_404(Contractor, pk=pk)
    stats = {
        'total_contracts': contractor.total_contracts,
        'active_contracts': contractor.active_contracts_count,
        'total_certified': float(contractor.total_certificates_amount),
        'total_payments': float(contractor.total_payments_amount),
        'outstanding': float(contractor.outstanding_amount),
    }
    return JsonResponse(stats)
