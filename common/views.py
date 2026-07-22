"""
Webhook endpoint لواتساب + البحث العام
"""

import hashlib
import hmac
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from common.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


@login_required
def global_search(request):
    """بحث عام عبر الكيانات الأساسية (حسابات، منتجات، عملاء، موردين)."""
    q = (request.GET.get('q') or '').strip()
    results = []
    if len(q) < 2:
        return JsonResponse({'results': results})

    from accounts.models import Account
    from purchases.models import Product, Supplier
    from sales.models import Customer

    limit = 8

    accounts = Account.objects.filter(name__icontains=q) | Account.objects.filter(code__icontains=q)
    for a in accounts.order_by('code')[:limit]:
        results.append({'type': 'حساب', 'name': a.name, 'code': a.code, 'url': f'/accounts/account/{a.id}/'})

    products = Product.objects.filter(name__icontains=q) | Product.objects.filter(code__icontains=q)
    for p in products.order_by('code')[:limit]:
        results.append({'type': 'منتج', 'name': p.name, 'code': p.code, 'url': '/purchases/products/'})

    customers = Customer.objects.filter(name__icontains=q) | Customer.objects.filter(code__icontains=q)
    for c in customers.order_by('code')[:limit]:
        results.append({'type': 'عميل', 'name': c.name, 'code': c.code, 'url': '/sales/customers/'})

    suppliers = Supplier.objects.filter(name__icontains=q) | Supplier.objects.filter(code__icontains=q)
    for s in suppliers.order_by('code')[:limit]:
        results.append({'type': 'مورد', 'name': s.name, 'code': s.code, 'url': '/purchases/suppliers/'})

    return JsonResponse({'results': results[: limit * 2]})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def whatsapp_webhook(request):
    """
    Webhook endpoint لـ WhatsApp Business API

    GET: التحقق من الاشتراك (Verification)
    POST: استلام التحديثات (Status updates, incoming messages)
    """
    service = WhatsAppService()

    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        expected_token = getattr(settings, 'WHATSAPP_WEBHOOK_VERIFY_TOKEN', '')
        if mode == 'subscribe' and token and hmac.compare_digest(str(token), str(expected_token)):
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('Forbidden', status=403)

    token = request.headers.get('X-Hub-Signature-256', '')
    expected_secret = getattr(settings, 'WHATSAPP_WEBHOOK_SECRET', '')
    # fail-closed: رفض صريح عند عدم ضبط السر أو عدم تطابق التوقيع
    if not expected_secret or not hmac.compare_digest(
        token, 'sha256=' + hmac.new(expected_secret.encode(), request.body, hashlib.sha256).hexdigest()
    ):
        return JsonResponse({'error': 'invalid signature'}, status=403)

    try:
        result = service.handle_webhook(request)
        return JsonResponse(result)
    except Exception:
        logger.exception('Webhook error')
        return JsonResponse({'success': False, 'error': 'internal error'}, status=500)
