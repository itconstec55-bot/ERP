import json
from datetime import datetime

from celery import shared_task

from .models import MachineInfo, SyncLog
from .sync_engine import export_data, recalculate_balances


@shared_task
def recalc_balances_task():
    """إعادة حساب الأرصدة/المخزون بشكل غير متزامن (أو متزامن في وضع eager)."""
    recalculate_balances()
    return 'balances recalculated'


@shared_task
def perform_manual_sync(log_id, host_address, host_port, api_key, machine_id):
    """تنفيذ المزامنة اليدوية في الخلفية (أو متزامن في وضع eager).

    يُرسل بيانات الجهاز للـ Host ويحدّث سجل المزامنة. عند توفّر وسيط (Redis)
    وضبط DJANGO_CELERY_EAGER=False يُنفَّذ خارج طلب HTTP فعلياً.
    """
    log = SyncLog.objects.get(pk=log_id)
    try:
        export = export_data(machine_id)
        export_json = json.dumps(export, ensure_ascii=False, default=str)

        import urllib.error
        import urllib.request

        url = f'http://{host_address}:{host_port}/api/sync/push/'
        req = urllib.request.Request(
            url, data=export_json.encode('utf-8'), headers={'Content-Type': 'application/json', 'X-API-Key': api_key}
        )
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode())

        log.records_sent = export['sync_manifest']['record_count']
        log.records_received = result.get('imported', 0)
        log.conflicts_found = result.get('conflicts', 0)
        log.status = 'completed'
        log.completed_at = datetime.now()
        log.sync_data = result
        log.save()

        machine = MachineInfo.objects.filter(machine_id=machine_id).first()
        if machine:
            machine.last_sync_at = datetime.now()
            machine.save(update_fields=['last_sync_at'])

        return 'sync completed'
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
        log.completed_at = datetime.now()
        log.save()
        raise
