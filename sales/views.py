from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, models, transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.accounting_service import AccountNotFoundError, UnbalancedEntryError
from common.excel_utils import export_to_excel, import_from_excel
from common.permissions import can_access_branch, filter_by_user_branches, screen_permission_required
from common.whatsapp import send_invoice_whatsapp, send_statement_whatsapp
from purchases.models import Product

from .forms import CustomerForm, SalesInvoiceForm, SalesInvoiceLineFormSet
from .models import Customer, SalesInvoice

# الحد الأقصى لحجم ملف الاستيراد (10 ميجابايت)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
import logging

logger = logging.getLogger('accounting')


@screen_permission_required('sales.customer', 'view')
def customer_list(request):
    customers = Customer.objects.filter(is_active=True)
    paginator = Paginator(customers, 25)
    page = request.GET.get('page')
    customers_page = paginator.get_page(page)
    return render(request, 'sales/customer_list.html', {'customers': customers_page})


@screen_permission_required('sales.customer', 'add')
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء العميل بنجاح')
            return redirect('sales:customer_list')
    else:
        form = CustomerForm()
    return render(request, 'sales/customer_form.html', {'form': form})


@screen_permission_required('sales.customer', 'view')
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    invoices = SalesInvoice.objects.filter(customer=customer).select_related('journal_entry').order_by('-date')
    total_sales = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    return render(
        request, 'sales/customer_detail.html', {'customer': customer, 'invoices': invoices, 'total_sales': total_sales}
    )


@screen_permission_required('sales.customer', 'edit')
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل العميل بنجاح')
            return redirect('sales:customer_detail', pk=pk)
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'sales/customer_form.html', {'form': form, 'customer': customer})


@screen_permission_required('sales.invoice', 'view')
def sales_invoice_list(request):
    invoices = filter_by_user_branches(SalesInvoice.objects.select_related('customer', 'journal_entry'), request.user)
    paginator = Paginator(invoices, 25)
    page = request.GET.get('page')
    invoices_page = paginator.get_page(page)
    return render(request, 'sales/invoice_list.html', {'invoices': invoices_page})


@screen_permission_required('sales.invoice', 'add')
def sales_invoice_create(request):
    if request.method == 'POST':
        form = SalesInvoiceForm(request.POST)
        formset = SalesInvoiceLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.created_by = request.user
            from common.permissions import get_user_profile

            profile = get_user_profile(request.user)
            if profile and profile.branch:
                invoice.branch = profile.branch

            with transaction.atomic():
                from warehouses.models import WarehouseProduct

                stock_errors = []
                for f in formset:
                    if not f.cleaned_data or f.cleaned_data.get('DELETE'):
                        continue
                    product = f.cleaned_data.get('product')
                    quantity = f.cleaned_data.get('quantity', 0)
                    if product and quantity:
                        wp_list = WarehouseProduct.objects.select_for_update().filter(product=product)
                        total_stock = wp_list.aggregate(total=models.Sum('quantity'))['total'] or 0
                        if total_stock < quantity:
                            stock_errors.append(f'{product.name}: المتوفر {total_stock}، المطلوب {quantity}')
                if stock_errors:
                    for err in stock_errors:
                        messages.error(request, f'نقص في المخزون - {err}')
                    return redirect('sales:invoice_create')

                invoice.save()
                formset.instance = invoice
                formset.save()
                invoice.calculate_totals()

            # invoice.calculate_totals() يُنفَّذ داخل الحصر الذرّي أعلاه

            customer = invoice.customer
            if customer and customer.credit_limit > 0:
                total_owed = (
                    SalesInvoice.objects.filter(customer=customer, remaining_amount__gt=0)
                    .exclude(pk=invoice.pk)
                    .aggregate(total=Sum('remaining_amount'))['total']
                    or 0
                )
                new_total = total_owed + invoice.remaining_amount
                if new_total > customer.credit_limit:
                    if getattr(settings, 'CREDIT_LIMIT_HARD_BLOCK', False):
                        invoice.delete()
                        messages.error(
                            request,
                            f'تم رفض الفاتورة: العميل تجاوز حد الائتمان ({customer.credit_limit:,.2f} ج.م). الرصيد المستحق المتوقع: {new_total:,.2f} ج.م',
                        )
                        return redirect('sales:invoice_create')
                    else:
                        messages.warning(
                            request,
                            f'تنبيه: العميل تجاوز حد الائتمان ({customer.credit_limit:,.2f} ج.م). الرصيد المستحق: {new_total:,.2f} ج.م',
                        )

            messages.success(request, 'تم إنشاء الفاتورة بنجاح')
            try:
                from notifications.utils import notify_invoice_created

                notify_invoice_created(invoice)
            except Exception:
                pass
            return redirect('sales:invoice_detail', pk=invoice.pk)
    else:
        form = SalesInvoiceForm()
        formset = SalesInvoiceLineFormSet()
    products = Product.objects.filter(is_active=True)
    return render(request, 'sales/invoice_form.html', {'form': form, 'formset': formset, 'products': products})


@screen_permission_required('sales.invoice', 'view')
def sales_invoice_detail(request, pk):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    if not can_access_branch(request.user, invoice.branch_id):
        messages.error(request, 'ليس لديك صلاحية على فاتورة هذا الفرع')
        return redirect('sales:invoice_list')
    lines = invoice.lines.select_related('product', 'product__category').all()
    return render(request, 'sales/invoice_detail.html', {'invoice': invoice, 'lines': lines})


@require_POST
@screen_permission_required('sales.invoice', 'edit')
def sales_invoice_approve(request, pk):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    try:
        invoice.approve(request.user)
        from audit.models import log_action

        log_action(
            request.user,
            'update',
            'sales.salesinvoice',
            object_id=invoice.pk,
            object_repr=str(invoice)[:200],
            changes={'approved': True},
            request=request,
        )
        messages.success(request, 'تم اعتماد الفاتورة بنجاح')
    except ValueError as e:
        messages.error(request, str(e))
        logger.exception('Approve failed for SalesInvoice %s', pk)
    return redirect('sales:invoice_detail', pk=pk)


@require_POST
@screen_permission_required('sales.invoice', 'edit')
def sales_invoice_bulk_approve(request):
    raw = request.POST.get('invoice_ids', '')
    ids = [x.strip() for x in raw.split(',') if x.strip()]
    if not ids:
        messages.warning(request, 'لم يتم تحديد أي فواتير')
        return redirect('sales:invoice_list')
    approved = 0
    for pk in ids:
        try:
            inv = SalesInvoice.objects.get(pk=pk)
            inv.approve(request.user)
            approved += 1
        except Exception:
            pass
    messages.success(request, f'تم اعتماد {approved} فاتورة من أصل {len(ids)}')
    return redirect('sales:invoice_list')


@require_POST
@screen_permission_required('sales.invoice', 'edit')
def sales_invoice_bulk_post(request):
    raw = request.POST.get('invoice_ids', '')
    ids = [x.strip() for x in raw.split(',') if x.strip()]
    if not ids:
        messages.warning(request, 'لم يتم تحديد أي فواتير')
        return redirect('sales:invoice_list')
    posted = 0
    errors = 0
    for pk in ids:
        try:
            inv = SalesInvoice.objects.get(pk=pk)
            inv.create_journal_entry()
            posted += 1
        except Exception:
            errors += 1
    msg = f'تم ترحيل {posted} فاتورة من أصل {len(ids)}'
    if errors:
        msg += f' ({errors} فشلت)'
    messages.success(request, msg)
    return redirect('sales:invoice_list')


@require_POST
@screen_permission_required('sales.invoice', 'edit')
def sales_invoice_post(request, pk):
    invoice = get_object_or_404(SalesInvoice, pk=pk)
    try:
        invoice.create_journal_entry()
        from audit.models import log_action

        log_action(
            request.user,
            'post',
            'sales.salesinvoice',
            object_id=invoice.pk,
            object_repr=str(invoice)[:200],
            request=request,
        )
        messages.success(request, 'تم ترحيل الفاتورة بنجاح')
        logger.info(f'Sales invoice {invoice.invoice_number} posted by user {request.user.username}')
        try:
            from notifications.utils import notify_invoice_posted

            notify_invoice_posted(invoice)
        except Exception:
            pass
    except UnbalancedEntryError:
        messages.error(request, 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.')
        logger.exception('Posting failed for SalesInvoice %s', pk)
    except AccountNotFoundError:
        messages.error(request, 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.')
        logger.exception('Posting failed for SalesInvoice %s', pk)
    except IntegrityError as e:
        messages.error(request, 'خطأ في سلامة البيانات - يرجى مراجعة الحسابات')
        logger.error(f'Integrity error posting invoice {invoice.pk}: {e}')
    except Exception:
        messages.error(request, 'حدث خطأ غير متوقع، يرجى المحاولة لاحقاً')
        logger.exception(f'Unexpected error posting invoice {invoice.pk}')
    return redirect('sales:invoice_detail', pk=pk)


@screen_permission_required('sales.invoice', 'print')
def sales_invoice_print(request, pk):
    from company.models import Company

    invoice = get_object_or_404(SalesInvoice, pk=pk)
    lines = invoice.lines.select_related('product').all()
    company = Company.objects.first()
    return render(
        request,
        'sales/invoice_print.html',
        {
            'invoice': invoice,
            'lines': lines,
            'company': company,
            'invoice_type': 'فاتورة مبيعات',
            'customer': invoice.customer,
        },
    )


@require_POST
@screen_permission_required('sales.invoice', 'print')
def sales_invoice_whatsapp(request, pk):
    """إرسال فاتورة مبيعات عبر واتساب"""
    invoice = get_object_or_404(SalesInvoice, pk=pk)

    # الحصول على رقم الهاتف (المحمول أولاً ثم التليفون)
    phone = invoice.customer.mobile or invoice.customer.phone

    if not phone:
        messages.error(request, 'لا يوجد رقم هاتف مسجل للعميل')
        return redirect('sales:invoice_detail', pk=pk)

    # إرسال عبر واتساب
    result = send_invoice_whatsapp(
        invoice=invoice, phone=phone, party_name=invoice.customer.name, party_type='customer'
    )

    if result['success']:
        if result['method'] == 'api':
            messages.success(request, 'تم إرسال الفاتورة عبر واتساب بنجاح')
        else:
            # فتح رابط wa.me في تبويب جديد
            messages.success(request, 'جاهز للإرسال - سيفتح الواتساب في تبويب جديد')
            # في حال كان طلب AJAX، إرجاع الرابط
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'link': result['link']})
            # إعادة توجيه للرابط
            return redirect(result['link'])
    else:
        messages.error(request, f'فشل الإرسال: {result["error"]}')

    return redirect('sales:invoice_detail', pk=pk)


@require_POST
@screen_permission_required('sales.customer', 'print')
def customer_statement_whatsapp(request, pk):
    """إرسال كشف حساب عميل عبر واتساب"""
    customer = get_object_or_404(Customer, pk=pk)

    phone = customer.mobile or customer.phone
    if not phone:
        messages.error(request, 'لا يوجد رقم هاتف مسجل للعميل')
        return redirect('sales:customer_detail', pk=pk)

    invoices = SalesInvoice.objects.filter(customer=customer).order_by('-date')

    result = send_statement_whatsapp(
        party=customer, invoices=invoices, phone=customer.mobile or customer.phone, party_type='customer'
    )

    if result['success']:
        if result['method'] == 'api':
            messages.success(request, 'تم إرسال كشف الحساب عبر واتساب بنجاح')
        else:
            messages.success(request, 'جاهز للإرسال - سيفتح الواتساب في تبويب جديد')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'link': result['link']})
            return redirect(result['link'])
    else:
        messages.error(request, f'فشل الإرسال: {result["error"]}')

    return redirect('sales:customer_detail', pk=pk)


@screen_permission_required('sales.customer', 'export')
def export_customers(request):
    customers = Customer.objects.all()
    return export_to_excel(
        customers,
        [
            {'field': 'code', 'header': 'الكود', 'width': 12},
            {'field': 'name', 'header': 'الاسم', 'width': 25},
            {'field': lambda c: c.get_customer_type_display(), 'header': 'النوع', 'width': 15},
            {'field': 'phone', 'header': 'التليفون', 'width': 15},
            {'field': 'email', 'header': 'البريد الإلكتروني', 'width': 20},
            {'field': 'tax_number', 'header': 'الرقم الضريبي', 'width': 15},
            {'field': 'current_balance', 'header': 'الرصيد', 'width': 15, 'format': '#,##0.00'},
        ],
        filename='customers',
    )


@screen_permission_required('sales.customer', 'add')
def import_customers(request):
    if request.method != 'POST':
        return redirect('sales:customer_list')
    file = request.FILES.get('excel_file')
    if not file:
        messages.error(request, 'يرجى اختيار ملف Excel')
        return redirect('sales:customer_list')
    if file.size > MAX_UPLOAD_SIZE:
        messages.error(request, f'حجم الملف يتجاوز الحد الأقصى ({MAX_UPLOAD_SIZE // (1024 * 1024)} ميجابايت)')
        return redirect('sales:customer_list')
    try:
        rows = import_from_excel(
            file,
            [
                {'field': 'code', 'header': 'الكود'},
                {'field': 'name', 'header': 'الاسم'},
                {'field': 'phone', 'header': 'التليفون'},
                {'field': 'email', 'header': 'البريد الإلكتروني'},
                {'field': 'tax_number', 'header': 'الرقم الضريبي'},
                {'field': 'current_balance', 'header': 'الرصيد', 'type': 'decimal'},
            ],
        )
        created = 0
        for row in rows:
            if not row.get('code') or not row.get('name'):
                continue
            Customer.objects.get_or_create(
                code=row['code'],
                defaults={
                    'name': row['name'],
                    'phone': row.get('phone', ''),
                    'email': row.get('email', ''),
                    'tax_number': row.get('tax_number', ''),
                    'current_balance': row.get('current_balance') or 0,
                },
            )
            created += 1
        messages.success(request, f'تم استيراد {created} عميل بنجاح')
    except Exception:
        messages.error(request, 'حدث خطأ أثناء الاستيراد. تأكد من صحة بيانات الملف وحاول مرة أخرى.')
        logger.exception('Import failed')
    return redirect('sales:customer_list')
