from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.excel_utils import export_to_excel, import_from_excel
from common.permissions import screen_permission_required

from .forms import CatalogSettingsForm, ProductForm, PurchaseInvoiceForm, PurchaseInvoiceLineFormSet, SupplierForm
from .models import CatalogSettings, Product, ProductCategory, PurchaseInvoice, Supplier, UnitOfMeasure

# الحد الأقصى لحجم ملف الاستيراد (10 ميجابايت)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
import logging

from common.accounting_service import AccountNotFoundError, UnbalancedEntryError
from common.whatsapp import WhatsAppService

logger = logging.getLogger('accounting')


@screen_permission_required('purchases.supplier', 'view')
def supplier_list(request):
    suppliers = Supplier.objects.filter(is_active=True)
    paginator = Paginator(suppliers, 25)
    page = request.GET.get('page')
    suppliers_page = paginator.get_page(page)
    return render(request, 'purchases/supplier_list.html', {'suppliers': suppliers_page})


@screen_permission_required('purchases.supplier', 'add')
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء المورد بنجاح')
            return redirect('purchases:supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'purchases/supplier_form.html', {'form': form})


@screen_permission_required('purchases.supplier', 'view')
def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    invoices = PurchaseInvoice.objects.filter(supplier=supplier).select_related('journal_entry').order_by('-date')
    total_purchases = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    return render(
        request,
        'purchases/supplier_detail.html',
        {'supplier': supplier, 'invoices': invoices, 'total_purchases': total_purchases},
    )


@screen_permission_required('purchases.supplier', 'edit')
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل المورد بنجاح')
            return redirect('purchases:supplier_detail', pk=pk)
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'purchases/supplier_form.html', {'form': form, 'supplier': supplier})


@screen_permission_required('purchases.product', 'view')
def product_list(request):
    products = Product.objects.filter(is_active=True).select_related('category')
    category = request.GET.get('category')
    if category:
        products = products.filter(category_id=category)
    categories = ProductCategory.objects.filter(is_active=True)
    paginator = Paginator(products, 25)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    return render(request, 'purchases/product_list.html', {'products': products_page, 'categories': categories})


@screen_permission_required('purchases.product', 'add')
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء المنتج بنجاح')
            return redirect('purchases:product_list')
    else:
        form = ProductForm()
    return render(request, 'purchases/product_form.html', {'form': form})


@screen_permission_required('purchases.product', 'edit')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل المنتج بنجاح')
            return redirect('purchases:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'purchases/product_form.html', {'form': form, 'product': product})


@screen_permission_required('purchases.product', 'edit')
def catalog_settings(request):
    settings = CatalogSettings.get_settings()
    if request.method == 'POST':
        form = CatalogSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم حفظ إعدادات الكتالوج بنجاح')
            return redirect('purchases:catalog_settings')
    else:
        form = CatalogSettingsForm(instance=settings)
    units_count = UnitOfMeasure.objects.count()
    categories_count = ProductCategory.objects.count()
    return render(
        request,
        'purchases/catalog_settings.html',
        {'form': form, 'units_count': units_count, 'categories_count': categories_count},
    )


@screen_permission_required('purchases.invoice', 'view')
def purchase_invoice_list(request):
    invoices = PurchaseInvoice.objects.select_related('supplier', 'journal_entry').all()
    paginator = Paginator(invoices, 25)
    page = request.GET.get('page')
    invoices_page = paginator.get_page(page)
    return render(request, 'purchases/invoice_list.html', {'invoices': invoices_page})


@screen_permission_required('purchases.invoice', 'add')
def purchase_invoice_create(request):
    if request.method == 'POST':
        form = PurchaseInvoiceForm(request.POST)
        formset = PurchaseInvoiceLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                invoice = form.save(commit=False)
                invoice.created_by = request.user
                invoice.save()
                formset.instance = invoice
                formset.save()
                invoice.calculate_totals()

            supplier = invoice.supplier
            if supplier and supplier.credit_limit > 0:
                total_owed = (
                    PurchaseInvoice.objects.filter(supplier=supplier, remaining_amount__gt=0)
                    .exclude(pk=invoice.pk)
                    .aggregate(total=Sum('remaining_amount'))['total']
                    or 0
                )
                new_total = total_owed + invoice.remaining_amount
                if new_total > supplier.credit_limit:
                    if getattr(settings, 'CREDIT_LIMIT_HARD_BLOCK', False):
                        invoice.delete()
                        messages.error(
                            request,
                            f'تم رفض الفاتورة: المورد تجاوز حد الائتمان ({supplier.credit_limit:,.2f} ج.م). الرصيد المستحق المتوقع: {new_total:,.2f} ج.م',
                        )
                        return redirect('purchases:purchase_invoice_create')
                    else:
                        messages.warning(
                            request,
                            f'تنبيه: المورد تجاوز حد الائتمان ({supplier.credit_limit:,.2f} ج.م). الرصيد المستحق: {new_total:,.2f} ج.م',
                        )

            messages.success(request, 'تم إنشاء الفاتورة بنجاح')
            try:
                from notifications.utils import notify_purchase_invoice_created

                notify_purchase_invoice_created(invoice)
            except Exception:
                pass
            return redirect('purchases:invoice_detail', pk=invoice.pk)
    else:
        form = PurchaseInvoiceForm()
        formset = PurchaseInvoiceLineFormSet()
    return render(request, 'purchases/invoice_form.html', {'form': form, 'formset': formset})


@screen_permission_required('purchases.invoice', 'view')
def purchase_invoice_detail(request, pk):
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    lines = invoice.lines.select_related('product', 'product__category').all()
    return render(request, 'purchases/invoice_detail.html', {'invoice': invoice, 'lines': lines})


@require_POST
@screen_permission_required('purchases.invoice', 'edit')
def purchase_invoice_approve(request, pk):
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    try:
        invoice.approve(request.user)
        from audit.models import log_action

        log_action(
            request.user,
            'update',
            'purchases.purchaseinvoice',
            object_id=invoice.pk,
            object_repr=str(invoice)[:200],
            changes={'approved': True},
            request=request,
        )
        messages.success(request, 'تم اعتماد الفاتورة بنجاح')
    except ValueError as e:
        messages.error(request, str(e))
        logger.exception('Approve failed for PurchaseInvoice %s', pk)
    return redirect('purchases:invoice_detail', pk=pk)


@require_POST
@screen_permission_required('purchases.invoice', 'edit')
def purchase_invoice_bulk_approve(request):
    raw = request.POST.get('invoice_ids', '')
    ids = [x.strip() for x in raw.split(',') if x.strip()]
    if not ids:
        messages.warning(request, 'لم يتم تحديد أي فواتير')
        return redirect('purchases:invoice_list')
    approved = 0
    for pk in ids:
        try:
            inv = PurchaseInvoice.objects.get(pk=pk)
            inv.approve(request.user)
            approved += 1
        except Exception:
            pass
    messages.success(request, f'تم اعتماد {approved} فاتورة من أصل {len(ids)}')
    return redirect('purchases:invoice_list')


@require_POST
@screen_permission_required('purchases.invoice', 'edit')
def purchase_invoice_bulk_post(request):
    raw = request.POST.get('invoice_ids', '')
    ids = [x.strip() for x in raw.split(',') if x.strip()]
    if not ids:
        messages.warning(request, 'لم يتم تحديد أي فواتير')
        return redirect('purchases:invoice_list')
    posted = 0
    errors = 0
    for pk in ids:
        try:
            inv = PurchaseInvoice.objects.get(pk=pk)
            inv.create_journal_entry()
            posted += 1
        except Exception:
            errors += 1
    msg = f'تم ترحيل {posted} فاتورة من أصل {len(ids)}'
    if errors:
        msg += f' ({errors} فشلت)'
    messages.success(request, msg)
    return redirect('purchases:invoice_list')


@require_POST
@screen_permission_required('purchases.invoice', 'edit')
def purchase_invoice_post(request, pk):
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    try:
        invoice.create_journal_entry()
        from audit.models import log_action

        log_action(
            request.user,
            'post',
            'purchases.purchaseinvoice',
            object_id=invoice.pk,
            object_repr=str(invoice)[:200],
            request=request,
        )
        messages.success(request, 'تم ترحيل الفاتورة بنجاح')
        logger.info(f'Purchase invoice {invoice.invoice_number} posted by user {request.user.username}')
        try:
            from notifications.utils import notify_purchase_invoice_posted

            notify_purchase_invoice_posted(invoice)
        except Exception:
            pass
    except UnbalancedEntryError:
        messages.error(request, 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.')
        logger.exception('Posting failed for PurchaseInvoice %s', pk)
    except AccountNotFoundError:
        messages.error(request, 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.')
        logger.exception('Posting failed for PurchaseInvoice %s', pk)
    except IntegrityError as e:
        messages.error(request, 'خطأ في سلامة البيانات - يرجى مراجعة الحسابات')
        logger.error(f'Integrity error posting invoice {invoice.pk}: {e}')
    except Exception:
        messages.error(request, 'حدث خطأ غير متوقع، يرجى المحاولة لاحقاً')
        logger.exception(f'Unexpected error posting invoice {invoice.pk}')
    return redirect('purchases:invoice_detail', pk=pk)


@screen_permission_required('purchases.invoice', 'print')
def purchase_invoice_print(request, pk):
    from company.models import Company

    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    lines = invoice.lines.select_related('product').all()
    company = Company.objects.first()
    return render(
        request,
        'purchases/invoice_print.html',
        {
            'invoice': invoice,
            'lines': lines,
            'company': company,
            'invoice_type': 'فاتورة مشتريات',
            'supplier': invoice.supplier,
        },
    )


@require_POST
@screen_permission_required('purchases.invoice', 'print')
def purchase_invoice_whatsapp(request, pk):
    """إرسال فاتورة المشتريات عبر واتساب للمورد"""
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    supplier = invoice.supplier

    # التحقق من وجود رقم هاتف
    phone = supplier.mobile or supplier.phone
    if not phone:
        messages.error(request, 'المورد ليس لديه رقم هاتف مسجل')
        return redirect('purchases:invoice_detail', pk=pk)

    # التحقق من صلاحية الرقم للواتساب
    is_valid, result = WhatsAppService.validate_phone_for_whatsapp(phone)
    if not is_valid:
        messages.error(request, f'رقم هاتف المورد غير صالح للواتساب: {result}')
        return redirect('purchases:invoice_detail', pk=pk)

    # توليد الرسالة
    message = WhatsAppService.format_invoice_message(invoice, invoice.supplier.name, party_type='supplier')

    # إنشاء رابط الواتساب
    wa_link = WhatsAppService.generate_wa_link(result, message)

    # في حالة وجود API، محاولة الإرسال المباشر
    if hasattr(settings, 'WHATSAPP_API_TOKEN') and settings.WHATSAPP_API_TOKEN:
        api_result = WhatsAppService().send_via_api(result, message)
        if api_result['success']:
            messages.success(request, 'تم إرسال الفاتورة عبر واتساب بنجاح ✓')
        else:
            # fallback to wa.me link
            messages.warning(request, f'تعذر الإرسال المباشر: {api_result["error"]}. سيتم فتح الرابط في المتصفح.')
            return redirect(wa_link)
    else:
        # استخدام رابط wa.me
        return redirect(wa_link)

    return redirect('purchases:invoice_detail', pk=pk)


@require_POST
@screen_permission_required('purchases.supplier', 'print')
def supplier_statement_whatsapp(request, pk):
    """إرسال كشف حساب المورد عبر واتساب"""
    supplier = get_object_or_404(Supplier, pk=pk)

    phone = supplier.mobile or supplier.phone
    if not phone:
        messages.error(request, 'المورد ليس لديه رقم هاتف مسجل')
        return redirect('purchases:supplier_detail', pk=pk)

    is_valid, result = WhatsAppService.validate_phone_for_whatsapp(phone)
    if not is_valid:
        messages.error(request, f'رقم هاتف المورد غير صالح للواتساب: {result}')
        return redirect('purchases:supplier_detail', pk=pk)

    # جلب الفواتير
    invoices = PurchaseInvoice.objects.filter(supplier=supplier).order_by('-date')
    if not invoices.exists():
        messages.error(request, 'لا توجد فواتير لهذا المورد')
        return redirect('purchases:supplier_detail', pk=pk)

    message = WhatsAppService.format_statement_message(supplier, invoices, party_type='supplier')
    wa_link = WhatsAppService.generate_wa_link(result, message)

    if hasattr(settings, 'WHATSAPP_API_TOKEN') and settings.WHATSAPP_API_TOKEN:
        api_result = WhatsAppService().send_via_api(result, message)
        if api_result['success']:
            messages.success(request, 'تم إرسال كشف الحساب عبر واتساب بنجاح ✓')
        else:
            messages.warning(request, f'تعذر الإرسال المباشر: {api_result["error"]}. سيتم فتح الرابط في المتصفح.')
            return redirect(wa_link)
    else:
        return redirect(wa_link)

    return redirect('purchases:supplier_detail', pk=pk)


@screen_permission_required('purchases.supplier', 'export')
def export_suppliers(request):
    suppliers = Supplier.objects.all()
    return export_to_excel(
        suppliers,
        [
            {'field': 'code', 'header': 'الكود', 'width': 12},
            {'field': 'name', 'header': 'الاسم', 'width': 25},
            {'field': lambda s: s.get_supplier_type_display(), 'header': 'النوع', 'width': 15},
            {'field': 'phone', 'header': 'التليفون', 'width': 15},
            {'field': 'email', 'header': 'البريد الإلكتروني', 'width': 20},
            {'field': 'tax_number', 'header': 'الرقم الضريبي', 'width': 15},
            {'field': 'current_balance', 'header': 'الرصيد', 'width': 15, 'format': '#,##0.00'},
        ],
        filename='suppliers',
    )


@screen_permission_required('purchases.supplier', 'add')
def import_suppliers(request):
    if request.method != 'POST':
        return redirect('purchases:supplier_list')
    file = request.FILES.get('excel_file')
    if not file:
        messages.error(request, 'يرجى اختيار ملف Excel')
        return redirect('purchases:supplier_list')
    if file.size > MAX_UPLOAD_SIZE:
        messages.error(request, f'حجم الملف يتجاوز الحد الأقصى ({MAX_UPLOAD_SIZE // (1024 * 1024)} ميجابايت)')
        return redirect('purchases:supplier_list')
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
            Supplier.objects.get_or_create(
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
        messages.success(request, f'تم استيراد {created} مورد بنجاح')
    except Exception:
        messages.error(request, 'حدث خطأ أثناء الاستيراد. تأكد من صحة بيانات الملف وحاول مرة أخرى.')
        logger.exception('Import failed')
    return redirect('purchases:supplier_list')


@screen_permission_required('purchases.product', 'export')
def export_products(request):
    products = Product.objects.select_related('category').all()
    return export_to_excel(
        products,
        [
            {'field': 'code', 'header': 'الكود', 'width': 12},
            {'field': 'name', 'header': 'الاسم', 'width': 25},
            {'field': lambda p: p.category.name if p.category else '', 'header': 'التصنيف', 'width': 15},
            {'field': 'purchase_price', 'header': 'سعر الشراء', 'width': 12, 'format': '#,##0.00'},
            {'field': 'selling_price', 'header': 'سعر البيع', 'width': 12, 'format': '#,##0.00'},
            {'field': 'current_stock', 'header': 'المخزون', 'width': 10},
            {'field': 'unit', 'header': 'الوحدة', 'width': 10},
        ],
        filename='products',
    )


@screen_permission_required('purchases.product', 'add')
def import_products(request):
    if request.method != 'POST':
        return redirect('purchases:product_list')
    file = request.FILES.get('excel_file')
    if not file:
        messages.error(request, 'يرجى اختيار ملف Excel')
        return redirect('purchases:product_list')
    if file.size > MAX_UPLOAD_SIZE:
        messages.error(request, f'حجم الملف يتجاوز الحد الأقصى ({MAX_UPLOAD_SIZE // (1024 * 1024)} ميجابايت)')
        return redirect('purchases:product_list')
    try:
        rows = import_from_excel(
            file,
            [
                {'field': 'code', 'header': 'الكود'},
                {'field': 'name', 'header': 'الاسم'},
                {'field': 'purchase_price', 'header': 'سعر الشراء', 'type': 'decimal'},
                {'field': 'selling_price', 'header': 'سعر البيع', 'type': 'decimal'},
                {'field': 'current_stock', 'header': 'المخزون', 'type': 'decimal'},
                {'field': 'unit', 'header': 'الوحدة'},
            ],
        )
        created = 0
        for row in rows:
            if not row.get('code') or not row.get('name'):
                continue
            unit_name = row.get('unit')
            unit_obj = UnitOfMeasure.objects.filter(name=unit_name).first() if unit_name else None
            Product.objects.get_or_create(
                code=row['code'],
                defaults={
                    'name': row['name'],
                    'purchase_price': row.get('purchase_price') or 0,
                    'selling_price': row.get('selling_price') or 0,
                    'current_stock': row.get('current_stock') or 0,
                    'unit': unit_name or 'قطعة',
                    'unit_of_measure': unit_obj,
                },
            )
            created += 1
        messages.success(request, f'تم استيراد {created} منتج بنجاح')
    except Exception:
        messages.error(request, 'حدث خطأ أثناء الاستيراد. تأكد من صحة بيانات الملف وحاول مرة أخرى.')
        logger.exception('Import failed')
    return redirect('purchases:product_list')


@screen_permission_required('purchases.product', 'print')
def product_barcode_print(request, pk):
    product = get_object_or_404(Product, pk=pk)
    barcode_value = product.barcode or product.code
    return render(request, 'purchases/product_barcode.html', {'product': product, 'barcode_value': barcode_value})


@screen_permission_required('purchases.product', 'print')
def product_barcode_batch(request):
    products = Product.objects.filter(is_active=True)
    if request.method == 'POST':
        product_ids = request.POST.getlist('products')
        count = int(request.POST.get('count', 1))
        selected = Product.objects.filter(pk__in=product_ids)
        labels = []
        for p in selected:
            for _ in range(count):
                labels.append(
                    {'name': p.name, 'code': p.code, 'barcode': p.barcode or p.code, 'price': p.selling_price}
                )
        return render(request, 'purchases/product_barcode_batch.html', {'labels': labels})
    return render(request, 'purchases/product_barcode_select.html', {'products': products})


@screen_permission_required('purchases.product', 'view')
def product_price_list(request):
    products = Product.objects.filter(is_active=True).select_related('category').order_by('category__name', 'code')
    return render(request, 'purchases/product_price_list.html', {'products': products})
