import logging
from datetime import date

from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.excel_utils import export_to_excel, import_from_excel
from common.permissions import screen_permission_required

from .forms import AssetCategoryForm, AssetForm, DepreciationEntryForm
from .models import Asset, AssetCategory, DepreciationEntry

logger = logging.getLogger('accounting')


@screen_permission_required('assets.asset', 'view')
def asset_list(request):
    assets = Asset.objects.filter(is_active=True).select_related('category')
    category = request.GET.get('category')
    if category:
        assets = assets.filter(category_id=category)
    categories = AssetCategory.objects.all()
    return render(request, 'assets/asset_list.html', {'assets': assets, 'categories': categories})


@screen_permission_required('assets.asset', 'add')
def asset_create(request):
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.created_by = request.user
            asset.net_book_value = asset.purchase_price
            asset.save()
            messages.success(request, 'تم إضافة الأصل بنجاح')
            return redirect('assets:asset_list')
    else:
        form = AssetForm()
    return render(request, 'assets/asset_form.html', {'form': form})


@screen_permission_required('assets.asset', 'view')
def asset_detail(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    depreciation_entries = DepreciationEntry.objects.filter(asset=asset).order_by('-date')
    return render(request, 'assets/asset_detail.html', {'asset': asset, 'depreciation_entries': depreciation_entries})


@screen_permission_required('assets.asset', 'edit')
def asset_edit(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل الأصل بنجاح')
            return redirect('assets:asset_detail', pk=pk)
    else:
        form = AssetForm(instance=asset)
    return render(request, 'assets/asset_form.html', {'form': form, 'asset': asset})


@screen_permission_required('assets.asset', 'add')
def depreciation_create(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if asset.status != 'active':
        messages.error(request, 'لا يمكن إنشاء إهلاك لأصل غير نشط')
        return redirect('assets:asset_detail', pk=asset_id)
    if request.method == 'POST':
        form = DepreciationEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.asset = asset
            entry.amount = asset.calculate_depreciation_for_period(entry.months)
            entry.created_by = request.user
            entry.save()
            entry.post_depreciation()
            messages.success(request, 'تم إنشاء قيد الإهلاك بنجاح')
            return redirect('assets:asset_detail', pk=asset_id)
    else:
        form = DepreciationEntryForm()
    return render(request, 'assets/depreciation_form.html', {'form': form, 'asset': asset})


@require_POST
@screen_permission_required('assets.asset', 'edit')
def asset_dispose(request, pk):
    """Asset disposal — creates journal entry and sets status to 'disposed'"""
    asset = get_object_or_404(Asset, pk=pk)
    if asset.status == 'disposed':
        messages.error(request, 'الأصل تم التخلص منه مسبقاً')
        return redirect('assets:asset_detail', pk=pk)

    from decimal import Decimal

    proceeds = Decimal(request.POST.get('proceeds', '0'))
    expense_note = request.POST.get('notes', f'التخلص من الأصل {asset.name}')

    from common.accounting_service import JournalEntryService

    with transaction.atomic():
        asset = Asset.objects.select_for_update().get(pk=asset.pk)

        gain_loss = proceeds - asset.net_book_value
        lines = []
        lines.append(
            {
                'account': asset.asset_account,
                'debit': 0,
                'credit': asset.net_book_value,
                'description': f'إلغاء الأصل {asset.name}',
            }
        )
        if asset.accumulated_depreciation > 0:
            lines.append(
                {
                    'account': asset.depr_account or JournalEntryService.get_account('1400'),
                    'debit': asset.accumulated_depreciation,
                    'credit': 0,
                    'description': f'إلغاء مجمع إهلاك {asset.name}',
                }
            )
        if proceeds > 0:
            lines.append(
                {
                    'account': JournalEntryService.get_account('1100'),  # cash/bank
                    'debit': proceeds,
                    'credit': 0,
                    'description': f'متحصلات بيع {asset.name}',
                }
            )
        if gain_loss > 0:
            lines.append(
                {
                    'account': JournalEntryService.get_account('3400'),  # gain on disposal
                    'debit': 0,
                    'credit': abs(gain_loss),
                    'description': f'أرباح بيع {asset.name}',
                }
            )
        elif gain_loss < 0:
            lines.append(
                {
                    'account': JournalEntryService.get_account('5300'),  # loss on disposal
                    'debit': abs(gain_loss),
                    'credit': 0,
                    'description': f'خسائر بيع {asset.name}',
                }
            )

        JournalEntryService.create_entry(
            entry_type='journal',
            date=date.today(),
            description=expense_note,
            reference=f'DSP-{asset.code}',
            lines=lines,
            created_by=request.user,
        )
        asset.status = 'disposed'
        asset.is_active = False
        asset.net_book_value = Decimal('0')
        asset.save(update_fields=['status', 'is_active', 'net_book_value'])

    messages.success(request, f'تم التخلص من الأصل {asset.name} بنجاح')
    return redirect('assets:asset_detail', pk=pk)


@screen_permission_required('assets.asset', 'view')
def asset_category_list(request):
    categories = AssetCategory.objects.annotate(accounts_count=Count('accounts')).all()
    return render(request, 'assets/category_list.html', {'categories': categories})


@screen_permission_required('assets.asset', 'add')
def asset_category_create(request):
    if request.method == 'POST':
        form = AssetCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء التصنيف بنجاح')
            return redirect('assets:category_list')
    else:
        form = AssetCategoryForm()
    return render(request, 'assets/category_form.html', {'form': form})


@screen_permission_required('assets.asset', 'export')
def export_assets(request):
    assets = Asset.objects.filter(is_active=True).select_related('category')
    return export_to_excel(
        assets,
        [
            {'field': 'code', 'header': 'كود الأصل', 'width': 15},
            {'field': 'name', 'header': 'اسم الأصل', 'width': 25},
            {'field': 'category', 'header': 'التصنيف', 'width': 20},
            {'field': 'purchase_price', 'header': 'سعر الشراء', 'width': 18},
            {'field': 'accumulated_depreciation', 'header': 'الإهلاك المتراكم', 'width': 18},
            {'field': 'status', 'header': 'الحالة', 'width': 15},
        ],
        filename='assets',
    )


@screen_permission_required('assets.asset', 'add')
def import_assets(request):
    if request.method != 'POST':
        return redirect('assets:asset_list')
    file = request.FILES.get('excel_file')
    if not file:
        messages.error(request, 'يرجى اختيار ملف Excel')
        return redirect('assets:asset_list')
    try:
        import uuid
        from datetime import date
        from decimal import Decimal

        from django.db import transaction

        columns = [
            {'field': 'code', 'header': 'كود الأصل'},
            {'field': 'name', 'header': 'اسم الأصل'},
            {'field': 'category', 'header': 'التصنيف'},
            {'field': 'purchase_price', 'header': 'سعر الشراء', 'type': 'decimal'},
            {'field': 'accumulated_depreciation', 'header': 'الإهلاك المتراكم', 'type': 'decimal'},
            {'field': 'status', 'header': 'الحالة'},
        ]
        rows = import_from_excel(file, columns)
        created = 0
        with transaction.atomic():
            for row in rows:
                price = row.get('purchase_price') or Decimal('0')
                dep = row.get('accumulated_depreciation') or Decimal('0')
                if price < 0 or dep < 0:
                    raise ValueError('لا يمكن أن يكون سعر الشراء أو الإهلاك المتراكم قيمة سالبة.')
                category_name = (row.get('category') or '').strip() or 'غير مصنف'
                category = AssetCategory.objects.filter(name=category_name).first()
                if category is None:
                    category = AssetCategory.objects.create(name=category_name)
                Asset.objects.create(
                    code=row.get('code') or f'IMP-{uuid.uuid4().hex[:8]}',
                    name=row.get('name') or 'غير محدد',
                    category=category,
                    purchase_date=date.today(),
                    purchase_price=price,
                    accumulated_depreciation=dep,
                    status=row.get('status', 'active') or 'active',
                    net_book_value=price - dep,
                )
                created += 1
        messages.success(request, f'تم استيراد {created} أصل بنجاح')
    except Exception:
        messages.error(request, 'حدث خطأ أثناء الاستيراد. تأكد من صحة بيانات الملف وحاول مرة أخرى.')
        logger.exception('Import failed')
    return redirect('assets:asset_list')
