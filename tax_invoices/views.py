from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from common.permissions import screen_permission_required
from sales.models import SalesInvoice

from .models import ETAConnection, TaxInvoice
from .services import ETAAPIError, ETAService


@screen_permission_required('tax_invoices.taxinvoice', 'view')
def tax_dashboard(request):
    """لوحة الفواتير الضريبية"""
    connections = ETAConnection.objects.all()
    active_conn = connections.filter(is_active=True).first()

    tax_invoices = TaxInvoice.objects.select_related('sales_invoice', 'connection').all()

    status_counts = {}
    for status, _ in TaxInvoice.SUBMISSION_STATUS_CHOICES:
        status_counts[status] = tax_invoices.filter(status=status).count()

    pending_count = tax_invoices.filter(status='pending').count()
    submitted_count = tax_invoices.filter(status__in=['submitted', 'valid']).count()
    failed_count = tax_invoices.filter(status__in=['failed', 'invalid']).count()

    # فواتير المبيعات غير المُرسلة بعد
    sent_ids = tax_invoices.values_list('sales_invoice_id', flat=True)
    unsent_invoices = (
        SalesInvoice.objects.filter(is_tax_invoice=True, is_posted=True).exclude(id__in=sent_ids).order_by('-date')[:20]
    )

    context = {
        'connections': connections,
        'active_conn': active_conn,
        'status_counts': status_counts,
        'pending_count': pending_count,
        'submitted_count': submitted_count,
        'failed_count': failed_count,
        'unsent_invoices': unsent_invoices,
        'total': tax_invoices.count(),
    }
    return render(request, 'tax_invoices/dashboard.html', context)


@screen_permission_required('tax_invoices.taxinvoice', 'view')
def connection_list(request):
    connections = ETAConnection.objects.all()
    return render(request, 'tax_invoices/connection_list.html', {'connections': connections})


@screen_permission_required('tax_invoices.taxinvoice', 'add')
def connection_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', 'الافتراضي')
        environment = request.POST.get('environment', 'sandbox')
        client_id = request.POST.get('client_id') or None
        client_secret = request.POST.get('client_secret') or None
        certificate_path = request.POST.get('certificate_path') or None
        certificate_password = request.POST.get('certificate_password') or None
        is_active = request.POST.get('is_active') == 'on'

        if is_active:
            ETAConnection.objects.filter(is_active=True).update(is_active=False)

        conn = ETAConnection.objects.create(
            name=name,
            environment=environment,
            client_id=client_id,
            client_secret=client_secret,
            certificate_path=certificate_path,
            certificate_password=certificate_password,
            is_active=is_active,
        )
        messages.success(request, 'تم إنشاء إعداد الاتصال بنجاح')
        return redirect('tax_invoices:connection_list')

    # التحقق من وجود إعداد افتراضي
    return render(request, 'tax_invoices/connection_form.html', {'environments': ETAConnection.ENVIRONMENT_CHOICES})


@screen_permission_required('tax_invoices.taxinvoice', 'edit')
def connection_edit(request, pk):
    conn = get_object_or_404(ETAConnection, pk=pk)
    if request.method == 'POST':
        conn.name = request.POST.get('name', conn.name)
        conn.environment = request.POST.get('environment', conn.environment)
        if request.POST.get('client_id'):
            conn.client_id = request.POST.get('client_id')
        if request.POST.get('client_secret'):
            conn.client_secret = request.POST.get('client_secret')
        conn.certificate_path = request.POST.get('certificate_path') or conn.certificate_path
        if request.POST.get('certificate_password'):
            conn.certificate_password = request.POST.get('certificate_password')
        conn.is_active = request.POST.get('is_active') == 'on'

        if conn.is_active:
            ETAConnection.objects.filter(is_active=True).exclude(pk=conn.pk).update(is_active=False)

        conn.save()
        messages.success(request, 'تم تحديث إعداد الاتصال بنجاح')
        return redirect('tax_invoices:connection_list')

    return render(
        request, 'tax_invoices/connection_form.html', {'conn': conn, 'environments': ETAConnection.ENVIRONMENT_CHOICES}
    )


@screen_permission_required('tax_invoices.taxinvoice', 'view')
def tax_invoice_list(request):
    tax_invoices = TaxInvoice.objects.select_related('sales_invoice', 'connection').all()

    status = request.GET.get('status')
    if status:
        tax_invoices = tax_invoices.filter(status=status)

    paginator = Paginator(tax_invoices, 25)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    return render(
        request,
        'tax_invoices/tax_invoice_list.html',
        {'tax_invoices': page_obj, 'status_choices': TaxInvoice.SUBMISSION_STATUS_CHOICES, 'current_status': status},
    )


@screen_permission_required('tax_invoices.taxinvoice', 'view')
def tax_invoice_detail(request, pk):
    tax_invoice = get_object_or_404(TaxInvoice, pk=pk)
    document = None
    try:
        document = tax_invoice.to_eta_document()
    except Exception as e:
        document = {'error': str(e)}

    return render(request, 'tax_invoices/tax_invoice_detail.html', {'tax_invoice': tax_invoice, 'document': document})


@require_POST
@screen_permission_required('tax_invoices.taxinvoice', 'add')
def tax_invoice_create_from_sales(request, sales_pk):
    """إنشاء فاتورة ضريبية من فاتورة مبيعات وإرسالها لمصلحة الضرائب"""
    sales_invoice = get_object_or_404(SalesInvoice, pk=sales_pk)

    active_conn = ETAConnection.objects.filter(is_active=True).first()
    if not active_conn:
        messages.error(request, 'لا يوجد إعداد اتصال مفعل لمصلحة الضرائب. يرجى إضافة إعداد أولاً.')
        return redirect('tax_invoices:connection_list')

    # التحقق من عدم وجود فاتورة ضريبية لنفس فاتورة المبيعات
    if TaxInvoice.objects.filter(sales_invoice=sales_invoice).exists():
        messages.warning(request, 'هذه الفاتورة سبق إرسالها لمصلحة الضرائب')
        return redirect('tax_invoices:tax_invoice_list')

    with transaction.atomic():
        tax_invoice = TaxInvoice.objects.create(
            tax_invoice_number=sales_invoice.invoice_number,
            sales_invoice=sales_invoice,
            connection=active_conn,
            document_type='i',
            total_sale_amount=sales_invoice.subtotal,
            total_discount_amount=sales_invoice.discount_amount,
            net_amount=sales_invoice.subtotal - sales_invoice.discount_amount,
            total_vat_amount=sales_invoice.vat_amount,
            total_amount=sales_invoice.total_amount,
            status='submitting',
            created_by=request.user,
        )

    # إرسال للمصلحة
    try:
        service = ETAService(active_conn)
        document = tax_invoice.to_eta_document()
        result = service.submit_documents(document)

        # معالجة الاستجابة
        if isinstance(result, list) and result:
            resp_item = result[0]
            tax_invoice.eta_uuid = resp_item.get('uuid')
            tax_invoice.eta_submission_uuid = resp_item.get('submissionUuid') or resp_item.get('submission_uuid')
            tax_invoice.status = 'submitted'
            tax_invoice.submitted_at = timezone.now()
            tax_invoice.submission_log = json_dumps_pretty(result)
            tax_invoice.save()

            messages.success(
                request, f'تم إرسال الفاتورة لمصلحة الضرائب. رقم المتابعة: {tax_invoice.eta_submission_uuid}'
            )
        elif isinstance(result, dict):
            tax_invoice.eta_uuid = result.get('uuid')
            tax_invoice.eta_submission_uuid = result.get('submissionUuid') or result.get('submission_uuid')
            tax_invoice.status = 'submitted'
            tax_invoice.submitted_at = timezone.now()
            tax_invoice.submission_log = json_dumps_pretty(result)
            tax_invoice.save()
            messages.success(request, 'تم إرسال الفاتورة لمصلحة الضرائب بنجاح')
        else:
            tax_invoice.status = 'failed'
            tax_invoice.error_message = 'استجابة غير متوقعة من مصلحة الضرائب'
            tax_invoice.submission_log = json_dumps_pretty(result)
            tax_invoice.save()
            messages.error(request, 'استجابة غير متوقعة من مصلحة الضرائب')

    except ETAAPIError as e:
        tax_invoice.status = 'failed'
        tax_invoice.error_message = e.message
        tax_invoice.submission_log = e.response_body
        tax_invoice.save()
        messages.error(request, f'فشل الإرسال: {e.message}')
    except Exception as e:
        tax_invoice.status = 'failed'
        tax_invoice.error_message = str(e)
        tax_invoice.save()
        messages.error(request, f'حدث خطأ غير متوقع: {e}')

    return redirect('tax_invoices:tax_invoice_detail', pk=tax_invoice.pk)


@require_POST
@screen_permission_required('tax_invoices.taxinvoice', 'edit')
def tax_invoice_check_status(request, pk):
    """متابعة حالة الفاتورة الضريبية من مصلحة الضرائب"""
    tax_invoice = get_object_or_404(TaxInvoice, pk=pk)

    if not tax_invoice.eta_submission_uuid:
        messages.error(request, 'لا يوجد رقم متابعة لهذه الفاتورة')
        return redirect('tax_invoices:tax_invoice_detail', pk=pk)

    try:
        service = ETAService(tax_invoice.connection)
        status_result = service.get_document_status(tax_invoice.eta_submission_uuid)

        # تحديث الحالة
        is_valid = status_result.get('is_valid', False)
        status_value = status_result.get('status', '').lower()
        if is_valid or status_value in ('valid', 'submitted', 'accepted'):
            tax_invoice.status = 'valid'
            tax_invoice.validated_at = timezone.now()
            # جلب التفاصيل الكاملة (الرقم الطويل + QR)
            if tax_invoice.eta_uuid:
                try:
                    details = service.get_document_details(tax_invoice.eta_uuid)
                    tax_invoice.eta_long_id = details.get('longId') or details.get('long_id')
                    tax_invoice.eta_internal_id = details.get('internalId') or details.get('internal_id')
                    tax_invoice.eta_qr_code = details.get('qrCode') or details.get('qr_code')
                    tax_invoice.eta_pdf_url = details.get('pdfUrl') or details.get('pdf_url')
                except ETAAPIError:
                    pass
            messages.success(request, 'الفاتورة صالحة ومقبولة من مصلحة الضرائب')
        else:
            tax_invoice.status = 'invalid'
            tax_invoice.error_message = json_dumps_pretty(status_result)[:2000]

        tax_invoice.submission_log = json_dumps_pretty(status_result)
        tax_invoice.save()

    except ETAAPIError as e:
        messages.error(request, f'فشل متابعة الحالة: {e.message}')
    except Exception as e:
        messages.error(request, f'حدث خطأ: {e}')

    return redirect('tax_invoices:tax_invoice_detail', pk=pk)


def json_dumps_pretty(obj):
    import json

    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(obj)


@require_POST
@screen_permission_required('tax_invoices.taxinvoice', 'edit')
def tax_invoice_void(request, pk):
    """إلغاء فاتورة ضريبية لدى مصلحة الضرائب"""
    tax_invoice = get_object_or_404(TaxInvoice, pk=pk)
    if tax_invoice.status == 'cancelled':
        messages.error(request, 'الفاتورة ملغاة مسبقاً')
        return redirect('tax_invoices:tax_invoice_detail', pk=pk)

    reason = request.POST.get('reason', 'تم الإلغاء يدوياً')
    try:
        if tax_invoice.connection and tax_invoice.eta_uuid:
            service = ETAService(tax_invoice.connection)
            service.void_document(tax_invoice.eta_uuid, reason=reason)
        tax_invoice.status = 'cancelled'
        tax_invoice.save()
        messages.success(request, 'تم إلغاء الفاتورة الضريبية بنجاح')
    except ETAAPIError as e:
        messages.error(request, f'فشل الإلغاء: {e.message}')
    return redirect('tax_invoices:tax_invoice_detail', pk=pk)
