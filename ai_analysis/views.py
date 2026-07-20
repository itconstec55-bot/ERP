from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.permissions import screen_permission_required

from .analyzer import AIAccountingAnalyzer
from .detector import AccountingErrorDetector
from .forms import AccountingErrorForm, ErrorLogFilterForm
from .models import ErrorLog, ErrorPattern, Solution


@screen_permission_required('ai_analysis.errorlog', 'view')
def dashboard(request):
    """لوحة تحكم تحليل الأخطاء"""
    # إحصائيات
    total_errors = ErrorLog.objects.count()
    critical_errors = ErrorLog.objects.filter(severity='critical').count()
    resolved_errors = ErrorLog.objects.filter(status='resolved').count()
    pending_errors = ErrorLog.objects.filter(status='pending').count()

    # آخر الأخطاء
    recent_errors = ErrorLog.objects.all()[:10]

    # أنماط الأخطاء المتكررة
    error_patterns = ErrorPattern.objects.filter(is_active=True)[:5]

    context = {
        'total_errors': total_errors,
        'critical_errors': critical_errors,
        'resolved_errors': resolved_errors,
        'pending_errors': pending_errors,
        'recent_errors': recent_errors,
        'error_patterns': error_patterns,
    }
    return render(request, 'ai_analysis/dashboard.html', context)


@screen_permission_required('ai_analysis.errorlog', 'add')
def analyze_error(request):
    """تحليل خطأ محاسبي"""
    if request.method == 'POST':
        form = AccountingErrorForm(request.POST)
        if form.is_valid():
            analyzer = AIAccountingAnalyzer()

            error_data = {
                'error_type': form.cleaned_data['error_type'],
                'reference_number': form.cleaned_data.get('reference_number', ''),
                'description': form.cleaned_data.get('description', ''),
                'affected_account_code': form.cleaned_data.get('account_code', ''),
                'amount': form.cleaned_data.get('amount', 0),
                'entry_date': form.cleaned_data.get('date_from'),
            }

            result = analyzer.analyze_single_error(error_data)

            if result['status'] == 'missing_data':
                messages.warning(request, 'بيانات غير كافية. يرجى توفير المزيد من المعلومات.')
                return render(
                    request,
                    'ai_analysis/analysis_form.html',
                    {'form': form, 'missing_data': result['missing_fields'], 'message': result['message']},
                )

            return render(request, 'ai_analysis/analysis_result.html', {'result': result, 'form': form})
    else:
        form = AccountingErrorForm()

    return render(request, 'ai_analysis/analysis_form.html', {'form': form})


@screen_permission_required('ai_analysis.errorlog', 'add')
def auto_detect(request):
    """كشف الأخطاء تلقائياً"""
    if request.method == 'POST':
        analyzer = AIAccountingAnalyzer()
        results = analyzer.auto_detect_and_analyze()
        messages.success(request, f'تم كشف {len(results)} خطأ محاسبي')
        return render(request, 'ai_analysis/detection_results.html', {'results': results})
    return render(request, 'ai_analysis/detection_results.html', {'results': [], 'show_scan_button': True})


@screen_permission_required('ai_analysis.errorlog', 'view')
def error_history(request):
    """سجل الأخطاء"""
    form = ErrorLogFilterForm(request.GET)
    errors = ErrorLog.objects.all()

    if form.is_valid():
        if form.cleaned_data.get('severity'):
            errors = errors.filter(severity=form.cleaned_data['severity'])
        if form.cleaned_data.get('status'):
            errors = errors.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('error_type'):
            errors = errors.filter(error_type__icontains=form.cleaned_data['error_type'])

    paginator = Paginator(errors, 25)
    page = request.GET.get('page')
    errors_page = paginator.get_page(page)

    context = {'errors': errors_page, 'form': form}
    return render(request, 'ai_analysis/error_history.html', context)


@screen_permission_required('ai_analysis.errorlog', 'view')
def error_detail(request, pk):
    """تفاصيل الخطأ"""
    error = get_object_or_404(ErrorLog, pk=pk)
    solutions = error.solutions.all()

    context = {'error': error, 'solutions': solutions}
    return render(request, 'ai_analysis/error_detail.html', context)


@screen_permission_required('ai_analysis.errorlog', 'edit')
@require_POST
def apply_solution(request, pk):
    """تطبيق حل مقترح"""
    solution = get_object_or_404(Solution, pk=pk)
    analyzer = AIAccountingAnalyzer()
    result = analyzer.apply_solution(pk, request.user)

    if result['status'] == 'success':
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('ai_analysis:error_detail', pk=solution.error_log.pk)


@screen_permission_required('ai_analysis.errorlog', 'add')
@require_POST
def api_detect_errors(request):
    """API: كشف الأخطاء تلقائياً"""
    detector = AccountingErrorDetector()
    errors = detector.scan_all()
    return JsonResponse({'errors': errors, 'count': len(errors)})


@screen_permission_required('ai_analysis.errorlog', 'add')
@require_POST
def api_analyze_error(request):
    """API: تحليل خطأ"""
    import json

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'بيانات غير صحيحة'}, status=400)

    analyzer = AIAccountingAnalyzer()
    result = analyzer.analyze_single_error(data)

    # تحويل ErrorLog إلى dict
    if 'error' in result and hasattr(result['error'], 'pk'):
        result['error_id'] = str(result['error'].pk)
        result['error_title'] = result['error'].title
        del result['error']

    return JsonResponse(result, safe=False)


@screen_permission_required('ai_analysis.errorlog', 'view')
def api_error_stats(request):
    """API: إحصائيات الأخطاء"""
    stats = {'total': ErrorLog.objects.count(), 'by_severity': {}, 'by_status': {}, 'by_type': {}}

    from django.db.models import Count

    for item in ErrorLog.objects.values('severity').annotate(count=Count('id')):
        stats['by_severity'][item['severity']] = item['count']

    for item in ErrorLog.objects.values('status').annotate(count=Count('id')):
        stats['by_status'][item['status']] = item['count']

    for item in ErrorLog.objects.values('error_type').annotate(count=Count('id')):
        stats['by_type'][item['error_type']] = item['count']

    return JsonResponse(stats)
