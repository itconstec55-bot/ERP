import json
import logging
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import SyncSettingsForm
from .models import MachineInfo, SyncLog, SyncSettings
from .sync_engine import create_sync_log, export_data, import_data

logger = logging.getLogger('accounting')


def _get_or_create_machine():
    machine_id = getattr(settings, 'MACHINE_ID', 'MACHINE-DEFAULT')
    machine, _ = MachineInfo.objects.get_or_create(
        machine_id=machine_id,
        defaults={
            'name': getattr(settings, 'MACHINE_NAME', 'الجهاز الرئيسي'),
            'machine_type': getattr(settings, 'MACHINE_TYPE', 'standalone'),
        },
    )
    return machine


def _verify_api_key(request):
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return False
    return MachineInfo.objects.filter(api_key=api_key, is_active=True).exists()


@login_required
def sync_dashboard(request):
    machine = _get_or_create_machine()
    sync_settings = SyncSettings.objects.first()
    if not sync_settings:
        sync_settings = SyncSettings.objects.create()

    recent_logs = SyncLog.objects.all()[:20]
    other_machines = MachineInfo.objects.exclude(pk=machine.pk)

    total_synced = SyncLog.objects.filter(status='completed').count()
    total_conflicts = sum(l.conflicts_found for l in recent_logs)

    context = {
        'machine': machine,
        'sync_settings': sync_settings,
        'recent_logs': recent_logs,
        'other_machines': other_machines,
        'total_synced': total_synced,
        'total_conflicts': total_conflicts,
    }
    return render(request, 'sync/sync_dashboard.html', context)


@login_required
def sync_settings_view(request):
    machine = _get_or_create_machine()
    sync_settings = SyncSettings.objects.first()
    if not sync_settings:
        sync_settings = SyncSettings.objects.create()

    if request.method == 'POST':
        form = SyncSettingsForm(request.POST, instance=sync_settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم حفظ إعدادات المزامنة بنجاح')
            return redirect('sync:sync_settings')
    else:
        form = SyncSettingsForm(instance=sync_settings)

    context = {'form': form, 'machine': machine, 'sync_settings': sync_settings}
    return render(request, 'sync/sync_settings.html', context)


@login_required
def test_connection(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    sync_settings = SyncSettings.objects.first()
    if not sync_settings or not sync_settings.host_address:
        return JsonResponse({'success': False, 'error': 'لم يتم تعيين عنوان الـ Host بعد'})

    import urllib.error
    import urllib.request

    url = f'http://{sync_settings.host_address}:{sync_settings.host_port}/api/sync/status/'
    api_key = sync_settings.sync_key

    try:
        req = urllib.request.Request(url, headers={'X-API-Key': api_key})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return JsonResponse({'success': True, 'data': data})
    except urllib.error.URLError:
        logger.exception('Connection test failed')
        return JsonResponse({'success': False, 'error': 'تعذر الاتصال بالسيرفر البعيد'})
    except Exception:
        logger.exception('Connection test failed')
        return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء اختبار الاتصال'})


@login_required
def manual_sync(request):
    if request.method != 'POST':
        return redirect('sync:sync_dashboard')

    sync_settings = SyncSettings.objects.first()
    machine = _get_or_create_machine()

    if not sync_settings or not sync_settings.host_address:
        messages.error(request, 'لم يتم تعيين عنوان الـ Host بعد')
        return redirect('sync:sync_settings')

    log = create_sync_log(machine, 'full', 'pending')

    # ضع مهمة المزامنة في الطابور. في وضع eager (الافتراضي، بلا وسيط) تُنفَّذ
    # متزامناً داخل الطلب فوراً؛ وعند ضبط وسيط + DJANGO_CELERY_EAGER=False تصبح غير متزامنة.
    from sync.tasks import perform_manual_sync

    perform_manual_sync.delay(
        str(log.id), sync_settings.host_address, sync_settings.host_port, sync_settings.sync_key, machine.machine_id
    )

    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        log.refresh_from_db()
        if log.status == 'completed':
            messages.success(
                request, f'تمت المزامنة بنجاح! تم إرسال {log.records_sent} سجل واستلام {log.records_received} سجل'
            )
        else:
            messages.error(request, 'فشلت المزامنة. تأكد من اتصال الشبكة وحاول مرة أخرى.')
    else:
        messages.info(request, 'جاري تنفيذ المزامنة في الخلفية... يمكنك متابعة السجلات.')

    return redirect('sync:sync_dashboard')


@login_required
def sync_log_detail(request, pk):
    log = get_object_or_404(SyncLog, pk=pk)
    return render(request, 'sync/sync_log_detail.html', {'log': log})


@csrf_exempt
@require_http_methods(['POST'])
def api_push(request):
    if not _verify_api_key(request):
        return JsonResponse({'error': 'مفتاح API غير صالح'}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'error': 'بيانات JSON غير صالحة'}, status=400)

    source_machine_id = data.get('sync_manifest', {}).get('source_machine', 'unknown')
    source_machine, _ = MachineInfo.objects.get_or_create(
        machine_id=source_machine_id, defaults={'name': f'جهاز {source_machine_id}', 'machine_type': 'client'}
    )

    log = create_sync_log(source_machine, 'push', 'pending')

    try:
        result = import_data(data, source_machine_id)

        log.records_received = result['imported']
        log.conflicts_found = len(result['errors'])
        log.status = 'completed'
        log.completed_at = datetime.now()
        log.sync_data = result
        log.save()

        source_machine.last_sync_at = datetime.now()
        source_machine.save(update_fields=['last_sync_at'])

        return JsonResponse(
            {
                'success': True,
                'imported': result['imported'],
                'skipped': result['skipped'],
                'conflicts': len(result['errors']),
                'errors': result['errors'][:10],
            }
        )

    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
        log.completed_at = datetime.now()
        log.save()
        logger.exception('Sync push failed')
        return JsonResponse({'error': 'حدث خطأ أثناء معالجة البيانات'}, status=500)


@csrf_exempt
@require_http_methods(['GET'])
def api_pull(request):
    if not _verify_api_key(request):
        return JsonResponse({'error': 'مفتاح API غير صالح'}, status=401)

    machine_id = request.GET.get('machine_id', settings.MACHINE_ID)

    # ترقيم النتائج لتفادي تحميل قاعدة البيانات كاملة دفعة واحدة
    limit = request.GET.get('limit')
    offset = request.GET.get('offset', '0')
    try:
        limit_val = int(limit) if limit else None
    except (TypeError, ValueError):
        limit_val = None
    if limit_val is not None:
        limit_val = max(1, min(limit_val, 5000))  # سقف أقصى للدفعة
    try:
        offset_val = max(0, int(offset))
    except (TypeError, ValueError):
        offset_val = 0

    try:
        data = export_data(machine_id, limit=limit_val, offset=offset_val)
        return JsonResponse(data)
    except Exception:
        logger.exception('Sync pull failed')
        return JsonResponse({'error': 'حدث خطأ أثناء جلب البيانات'}, status=500)


@csrf_exempt
@require_http_methods(['GET'])
def api_status(request):
    if not _verify_api_key(request):
        return JsonResponse({'error': 'مفتاح API غير صالح'}, status=401)

    machine = _get_or_create_machine()
    last_log = SyncLog.objects.first()

    return JsonResponse(
        {
            'machine_id': machine.machine_id,
            'name': machine.name,
            'machine_type': machine.machine_type,
            'last_sync': machine.last_sync_at.isoformat() if machine.last_sync_at else None,
            'last_log_status': last_log.status if last_log else None,
            'total_syncs': SyncLog.objects.filter(status='completed').count(),
        }
    )


@csrf_exempt
@require_http_methods(['POST'])
def api_recalculate(request):
    if not _verify_api_key(request):
        return JsonResponse({'error': 'مفتاح API غير صالح'}, status=401)

    try:
        from django.conf import settings

        from sync.tasks import recalc_balances_task

        result = recalc_balances_task.delay()
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            # وضع eager: نُفِّذت المهمة متزامنياً (لا وسيط) — النتيجة جاهزة
            return JsonResponse({'success': True, 'message': 'تم إعادة حساب الأرصدة بنجاح', 'task_id': result.id})
        return JsonResponse({'success': True, 'message': 'تم وضع مهمة إعادة الحساب في الطابور', 'task_id': result.id})
    except Exception:
        logger.exception('Recalculate balances failed')
        return JsonResponse({'error': 'حدث خطأ أثناء إعادة حساب الأرصدة'}, status=500)
