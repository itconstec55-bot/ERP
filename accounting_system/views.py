import json
import logging
import os
import sys
from datetime import datetime, timedelta

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

sys.path.insert(0, os.path.join(settings.BASE_DIR, 'deployment'))
from monitoring import get_all_metrics, save_metrics_history, get_metrics_history, get_service_status

logger = logging.getLogger('accounting')


def custom_server_error(request, template_name='500.html'):
    logger.error('Internal Server Error at %s', request.path, exc_info=True)
    return render(request, template_name, status=500)


@require_GET
def monitoring_dashboard(request):
    """System monitoring dashboard page."""
    return render(request, 'admin/monitoring_dashboard.html', {
        'page_title': 'لوحة المراقبة',
    })


@require_GET
def monitoring_api_metrics(request):
    """API endpoint: get current system metrics."""
    metrics = get_all_metrics()
    save_metrics_history(metrics)
    return JsonResponse(metrics)


@require_GET
def monitoring_api_history(request):
    """API endpoint: get metrics history for charts."""
    hours = int(request.GET.get('hours', 1))
    history = get_metrics_history(hours=hours)
    return JsonResponse({'history': history, 'hours': hours})


@require_GET
def monitoring_api_status(request):
    """API endpoint: get service status summary."""
    status = get_service_status()
    return JsonResponse(status)
