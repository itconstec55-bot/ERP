import json
from django.contrib.auth.decorators import login_required
from common.permissions import screen_permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction, IntegrityError
from .models import Company, CompanyBranch
from .forms import CompanyForm, CompanyBranchForm
from accounts.models import AccountType
from purchases.models import Product, ProductCategory, UnitOfMeasure
import logging

logger = logging.getLogger('accounting')


@login_required
def company_settings(request):
    company = Company.get_company()

    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم حفظ إعدادات الشركة بنجاح')
            return redirect('company:company_settings')
    else:
        form = CompanyForm(instance=company)

    branches = CompanyBranch.objects.filter(company=company)

    context = {
        'form': form,
        'company': company,
        'branches': branches,
    }
    return render(request, 'company/company_settings.html', context)


@login_required
def branch_create(request):
    company = Company.get_company()
    if request.method == 'POST':
        form = CompanyBranchForm(request.POST)
        if form.is_valid():
            branch = form.save(commit=False)
            branch.company = company
            branch.save()
            messages.success(request, 'تم إنشاء الفرع بنجاح')
            return redirect('company:company_settings')
    else:
        form = CompanyBranchForm()

    return render(request, 'company/branch_form.html', {'form': form})


@login_required
def branch_edit(request, pk):
    branch = get_object_or_404(CompanyBranch, pk=pk)
    if request.method == 'POST':
        form = CompanyBranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الفرع بنجاح')
            return redirect('company:company_settings')
    else:
        form = CompanyBranchForm(instance=branch)

    return render(request, 'company/branch_form.html', {'form': form, 'branch': branch})


@login_required
@require_POST
def branch_delete(request, pk):
    branch = get_object_or_404(CompanyBranch, pk=pk)
    branch.delete()
    messages.success(request, 'تم حذف الفرع بنجاح')
    return redirect('company:company_settings')


# ==================== إعدادات الإدارة (Admin Settings) ====================

@login_required
@screen_permission_required('accounts.account', 'edit')
def admin_settings_dashboard(request):
    """لوحة إعدادات الإدارة الرئيسية"""
    account_types = AccountType.objects.all().order_by('code')
    products = Product.objects.select_related('category', 'unit_of_measure').all().order_by('code')
    categories = ProductCategory.objects.all().order_by('code')
    units = UnitOfMeasure.objects.all().order_by('code')
    
    context = {
        'account_types': account_types,
        'products': products,
        'categories': categories,
        'units': units,
        'active_tab': request.GET.get('tab', 'account_types'),
    }
    return render(request, 'company/settings/admin_settings.html', context)


@login_required
@screen_permission_required('accounts.account', 'edit')
@require_http_methods(["POST"])
def account_type_create(request):
    """إنشاء نوع حساب جديد"""
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            account_type = AccountType.objects.create(
                code=data.get('code', '').strip().upper(),
                name=data.get('name', '').strip(),
                account_type=data.get('account_type', 'asset'),
                description=data.get('description', '').strip(),
                is_active=data.get('is_active', True),
            )
        return JsonResponse({
            'success': True,
            'message': 'تم إنشاء نوع الحساب بنجاح',
            'data': {
                'id': str(account_type.id),
                'code': account_type.code,
                'name': account_type.name,
                'account_type': account_type.account_type,
                'account_type_display': account_type.get_account_type_display(),
                'description': account_type.description,
                'is_active': account_type.is_active,
                'created_at': account_type.created_at.isoformat(),
            }
        })
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('accounts.account', 'edit')
@require_http_methods(["POST", "PATCH"])
def account_type_update(request, pk):
    """تحديث نوع حساب"""
    account_type = get_object_or_404(AccountType, pk=pk)
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            account_type.code = data.get('code', account_type.code).strip().upper()
            account_type.name = data.get('name', account_type.name).strip()
            account_type.account_type = data.get('account_type', account_type.account_type)
            account_type.description = data.get('description', account_type.description).strip()
            account_type.is_active = data.get('is_active', account_type.is_active)
            account_type.save()
        return JsonResponse({
            'success': True,
            'message': 'تم تحديث نوع الحساب بنجاح',
            'data': {
                'id': str(account_type.id),
                'code': account_type.code,
                'name': account_type.name,
                'account_type': account_type.account_type,
                'account_type_display': account_type.get_account_type_display(),
                'description': account_type.description,
                'is_active': account_type.is_active,
                'updated_at': account_type.updated_at.isoformat(),
            }
        })
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('accounts.account', 'delete')
@require_http_methods(["POST"])
def account_type_delete(request, pk):
    """حذف نوع حساب"""
    account_type = get_object_or_404(AccountType, pk=pk)
    try:
        # التح من وجود حسابات مرتبطية
        if account_type.accounts.exists():
            return JsonResponse({
                'success': False, 
                'message': 'لا يمكن الحذف: يوجد حسابات مرتبطية بهذا النوع'
            }, status=400)
        account_type.delete()
        return JsonResponse({'success': True, 'message': 'تم حذف نوع الحساب بنجاح'})
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'edit')
@require_http_methods(["POST"])
def product_create(request):
    """إنشاء منتج جديد"""
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            category = None
            if data.get('category_id'):
                category = get_object_or_404(ProductCategory, pk=data['category_id'])
            
            unit = None
            if data.get('unit_id'):
                unit = get_object_or_404(UnitOfMeasure, pk=data['unit_id'])
            
            product = Product.objects.create(
                code=data.get('code', '').strip().upper(),
                name=data.get('name', '').strip(),
                category=category,
                unit_of_measure=unit,
                unit=data.get('unit', 'قطعة').strip(),
                description=data.get('description', '').strip(),
                purchase_price=data.get('purchase_price', 0),
                selling_price=data.get('selling_price', 0),
                current_stock=data.get('current_stock', 0),
                minimum_stock=data.get('minimum_stock', 0),
                vat_rate=data.get('vat_rate', 14),
                is_active=data.get('is_active', True),
            )
        return JsonResponse({
            'success': True,
            'message': 'تم إنشاء المنتج بنجاح',
            'data': {
                'id': str(product.id),
                'code': product.code,
                'name': product.name,
                'category': product.category.name if product.category else '',
                'unit': product.unit,
                'purchase_price': float(product.purchase_price),
                'selling_price': float(product.selling_price),
                'current_stock': float(product.current_stock),
                'is_active': product.is_active,
                'created_at': product.created_at.isoformat(),
            }
        })
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'edit')
@require_http_methods(["POST"])
def product_update(request, pk):
    """تحديث منتج"""
    product = get_object_or_404(Product, pk=pk)
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            if data.get('category_id'):
                product.category = get_object_or_404(ProductCategory, pk=data['category_id'])
            else:
                product.category = None
                
            if data.get('unit_id'):
                product.unit_of_measure = get_object_or_404(UnitOfMeasure, pk=data['unit_id'])
            else:
                product.unit_of_measure = None
            
            product.code = data.get('code', product.code).strip().upper()
            product.name = data.get('name', product.name).strip()
            product.unit = data.get('unit', product.unit).strip()
            product.description = data.get('description', product.description).strip()
            product.purchase_price = data.get('purchase_price', product.purchase_price)
            product.selling_price = data.get('selling_price', product.selling_price)
            product.current_stock = data.get('current_stock', product.current_stock)
            product.minimum_stock = data.get('minimum_stock', product.minimum_stock)
            product.vat_rate = data.get('vat_rate', product.vat_rate)
            product.is_active = data.get('is_active', product.is_active)
            product.save()
        return JsonResponse({
            'success': True,
            'message': 'تم تحديث المنتج بنجاح',
            'data': {
                'id': str(product.id),
                'code': product.code,
                'name': product.name,
                'category': product.category.name if product.category else '',
                'unit': product.unit,
                'purchase_price': float(product.purchase_price),
                'selling_price': float(product.selling_price),
                'current_stock': float(product.current_stock),
                'is_active': product.is_active,
                'updated_at': product.updated_at.isoformat(),
            }
        })
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'delete')
@require_http_methods(["POST"])
def product_delete(request, pk):
    """حذف منتج"""
    product = get_object_or_404(Product, pk=pk)
    try:
        product.delete()
        return JsonResponse({'success': True, 'message': 'تم حذف المنتج بنجاح'})
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'edit')
@require_http_methods(["POST"])
def category_create(request):
    """إنشاء تصنيف منتج"""
    try:
        data = json.loads(request.body)
        category = ProductCategory.objects.create(
            code=data.get('code', '').strip().upper(),
            name=data.get('name', '').strip(),
            description=data.get('description', '').strip(),
            is_active=data.get('is_active', True),
        )
        return JsonResponse({
            'success': True,
            'message': 'تم إنشاء التصنيف بنجاح',
            'data': {
                'id': str(category.id),
                'code': category.code,
                'name': category.name,
                'description': category.description,
                'is_active': category.is_active,
            }
        })
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'edit')
@require_http_methods(["POST"])
def category_update(request, pk):
    """تحديث تصنيف منتج"""
    category = get_object_or_404(ProductCategory, pk=pk)
    try:
        data = json.loads(request.body)
        category.code = data.get('code', category.code).strip().upper()
        category.name = data.get('name', category.name).strip()
        category.description = data.get('description', category.description).strip()
        category.is_active = data.get('is_active', category.is_active)
        category.save()
        return JsonResponse({
            'success': True,
            'message': 'تم تحديث التصنيف بنجاح',
            'data': {
                'id': str(category.id),
                'code': category.code,
                'name': category.name,
                'description': category.description,
                'is_active': category.is_active,
            }
        })
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'delete')
@require_http_methods(["POST"])
def category_delete(request, pk):
    """حذف تصنيف منتج"""
    category = get_object_or_404(ProductCategory, pk=pk)
    try:
        if category.product_set.exists():
            return JsonResponse({
                'success': False, 
                'message': 'لا يمكن الحذف: يوجد منتجات مرتبطية بهذا التصنيف'
            }, status=400)
        category.delete()
        return JsonResponse({'success': True, 'message': 'تم حذف التصنيف بنجاح'})
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'edit')
@require_http_methods(["POST"])
def unit_create(request):
    """إنشاء وحدة قياس"""
    try:
        data = json.loads(request.body)
        unit = UnitOfMeasure.objects.create(
            code=data.get('code', '').strip().upper(),
            name=data.get('name', '').strip(),
            symbol=data.get('symbol', '').strip(),
            is_active=data.get('is_active', True),
        )
        return JsonResponse({
            'success': True,
            'message': 'تم إنشاء الوحدة بنجاح',
            'data': {
                'id': str(unit.id),
                'code': unit.code,
                'name': unit.name,
                'symbol': unit.symbol,
                'is_active': unit.is_active,
            }
        })
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'edit')
@require_http_methods(["POST"])
def unit_update(request, pk):
    """تحديث وحدة قياس"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    try:
        data = json.loads(request.body)
        unit.code = data.get('code', unit.code).strip().upper()
        unit.name = data.get('name', unit.name).strip()
        unit.symbol = data.get('symbol', unit.symbol).strip()
        unit.is_active = data.get('is_active', unit.is_active)
        unit.save()
        return JsonResponse({
            'success': True,
            'message': 'تم تحديث الوحدة بنجاح',
            'data': {
                'id': str(unit.id),
                'code': unit.code,
                'name': unit.name,
                'symbol': unit.symbol,
                'is_active': unit.is_active,
            }
        })
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)


@login_required
@screen_permission_required('purchases.product', 'delete')
@require_http_methods(["POST"])
def unit_delete(request, pk):
    """حذف وحدة قياس"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    try:
        if unit.products.exists():
            return JsonResponse({
                'success': False, 
                'message': 'لا يمكن الحذف: يوجد منتجات مرتبطية بهذه الوحدة'
            }, status=400)
        unit.delete()
        return JsonResponse({'success': True, 'message': 'تم حذف الوحدة بنجاح'})
    except IntegrityError:
        logger.exception('API operation failed (IntegrityError)')
        return JsonResponse({'success': False, 'message': 'تعارض في البيانات: الكود مكرر أو قيد غير صالح'}, status=400)
    except Exception as e:
        logger.exception('API operation failed')
        return JsonResponse({'success': False, 'message': 'خطأ في العملية'}, status=400)
