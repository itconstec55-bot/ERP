"""
Middleware مركزي لمعالجة الأخطاء وتتبع الطلبات
"""
import logging
import time
import traceback
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.utils.deprecation import MiddlewareMixin

from common.exceptions import AccountingError

logger = logging.getLogger('accounting')
request_logger = logging.getLogger('accounting.request')


class CSPMiddleware(MiddlewareMixin):
    """إضافة رأس Content-Security-Policy لحماية من هجمات XSS."""

    CSP_POLICY = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; img-src 'self' data:; font-src 'self' https://cdnjs.cloudflare.com; connect-src 'self'"

    def process_response(self, request: HttpRequest, response: HttpResponse) -> Optional[HttpResponse]:
        if not getattr(settings, 'DEBUG', True):
            response['Content-Security-Policy'] = self.CSP_POLICY
        return response


class IdleSessionTimeoutMiddleware(MiddlewareMixin):
    """تسجيل خروج المستخدم تلقائياً عند عدم النشاط لمدة 30 دقيقة."""

    IDLE_TIMEOUT = 30 * 60  # 30 minutes

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        if hasattr(request, 'user') and request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            now = time.time()
            if last_activity and (now - last_activity) > self.IDLE_TIMEOUT:
                logger.info('Idle session timeout for user %s', request.user.pk)
                from django.contrib.auth import logout
                logout(request)
                return
            request.session['last_activity'] = now


class SessionTrackingMiddleware(MiddlewareMixin):
    """Store IP address and user agent in the session for session management."""

    def _get_client_ip(self, request: HttpRequest) -> str:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def process_request(self, request: HttpRequest) -> None:
        if hasattr(request, 'user') and request.user.is_authenticated:
            ip = self._get_client_ip(request)
            ua = request.META.get('HTTP_USER_AGENT', '')[:500]
            if request.session.get('ip_address') != ip or request.session.get('user_agent') != ua:
                request.session['ip_address'] = ip
                request.session['user_agent'] = ua


class LoginThrottleMiddleware(MiddlewareMixin):
    """
    تقييد معدل محاولات تسجيل الدخول الفاشلة لمنع القوة الغاشمة (Brute Force).
    يحتسب المحاولات الفاشلة لكل عنوان IP ضمن نافذة زمنية، ويحظر مؤقتاً عند تجاوز الحد.

    ملاحظة: يستخدم LocMemCache (الذي يُعيد Django استخدامه افتراضياً)،这意味着 العداد
    محلي لكل عملية Gunicorn. في بيئة إنتاج متعددة العمليات، يجب استخدام Redis
    أو Memcached كخزّان مؤقت مشترك عبر CACHES setting.
    """
    MAX_ATTEMPTS = 10
    WINDOW = 300       # ثوانٍ لإعادة ضبط العداد
    BLOCK = 300        # ثوانٍ مدة الحظر عند تجاوز الحد

    def _ip(self, request: HttpRequest) -> str:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        login_paths = (getattr(settings, 'LOGIN_URL', '/accounts/login/'), '/admin/login/')
        if request.method != 'POST' or request.path not in login_paths:
            return response

        ip = self._ip(request)
        key = f'login_throttle:{ip}'
        now = time.time()
        data = cache.get(key) or {'count': 0, 'blocked_until': 0.0}

        # محظور حالياً
        if data.get('blocked_until') and now < data['blocked_until']:
            logger.warning('Blocked login attempt from %s (throttled)', ip)
            return HttpResponse(
                'تجاوزت عدد محاولات الدخول المسموح. يرجى المحاولة بعد بضع دقائق.',
                status=429,
            )

        # Django login view يعيد 200 عند فشل الدخول (إعادة عرض النموذج)
        # ويعيد 302 عند نجاح الدخول (إعادة توجيه)
        if response.status_code == 200:
            data['count'] = data.get('count', 0) + 1
            if data['count'] >= self.MAX_ATTEMPTS:
                data['blocked_until'] = now + self.BLOCK
                data['count'] = 0
                logger.warning('Login throttled for IP %s after %d attempts', ip, self.MAX_ATTEMPTS)
            cache.set(key, data, int(self.WINDOW + self.BLOCK))
            # إعادة فحص بعد التحديث للتأكد من أن المستخدم غير محظور الآن
            if data.get('blocked_until') and now < data['blocked_until']:
                return HttpResponse(
                    'تجاوزت عدد محاولات الدخول المسموح. يرجى المحاولة بعد بضع دقائق.',
                    status=429,
                )
        elif response.status_code in (302, 303):
            # نجاح الدخول: إعادة ضبط العداد
            cache.delete(key)

        return response


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Middleware لمعالجة الأخطاء غير المتوقعة وتخطي الطلبات.
    - يلتقط AccountingError ويحولها إلى استجابات مناسبة
    - يسجل الأخطاء غير المتوقعة في السجل المركزي
    - لا يكشف تفاصيل الأخطاء الداخلية للمستخدم
    """

    def process_exception(self, request, exception):
        if isinstance(exception, AccountingError):
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse(
                    {'error': exception.message, 'code': exception.code},
                    status=400,
                )
            from django.contrib import messages
            messages.error(request, exception.message)
            return None

        if isinstance(exception, PermissionError):
            logger.warning(
                'Permission denied: %s %s user=%s',
                request.method, request.path,
                request.user.pk if request.user.is_authenticated else 'anon',
            )
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'error': 'ليس لديك صلاحية لتنفيذ هذا الإجراء'}, status=403)
            from django.contrib import messages
            messages.error(request, 'ليس لديك صلاحية لتنفيذ هذا الإجراء')
            return None

        if isinstance(exception, FileNotFoundError):
            logger.error('File not found: %s', request.path, exc_info=True)
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'error': 'الملف المطلوب غير موجود'}, status=404)
            from django.contrib import messages
            messages.error(request, 'الملف المطلوب غير موجود')
            return None

        logger.exception(
            'Unhandled exception: %s %s user=%s',
            request.method, request.path,
            request.user.pk if request.user.is_authenticated else 'anon',
        )
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'error': 'حدث خطأ داخلي'}, status=500)
        return None


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware لتسجيل تفاصيل الطلبات البطيئة والأخطاء.
    """

    SLOW_REQUEST_THRESHOLD_MS = 2000

    def process_request(self, request):
        request._start_time = time.monotonic()

    def process_response(self, request, response):
        if not hasattr(request, '_start_time'):
            return response

        duration_ms = (time.monotonic() - request._start_time) * 1000
        status = response.status_code
        method = request.method
        path = request.path
        user = request.user.pk if hasattr(request, 'user') and request.user.is_authenticated else 'anon'

        if status >= 500:
            logger.error(
                '%s %s %d %.1fms user=%s',
                method, path, status, duration_ms, user,
            )
        elif duration_ms > self.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                'Slow request: %s %s %d %.1fms user=%s',
                method, path, status, duration_ms, user,
            )
        elif status >= 400:
            request_logger.info(
                '%s %s %d %.1fms user=%s',
                method, path, status, duration_ms, user,
            )

        return response


class TwoFactorAuthMiddleware(MiddlewareMixin):
    """
    Middleware لإلزام المستخدمين بالتحقق من المصادقة الثنائية بعد تسجيل الدخول.
    يعمل فقط إذا كان REQUIRE_2FA = True في settings.
    """

    EXEMPT_PATHS = (
        '/accounts/login/',
        '/logout/',
        '/admin/',
        '/api/',
        '/health/',
        '/static/',
        '/media/',
        '/users/2fa/',
    )

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not getattr(settings, 'REQUIRE_2FA', False):
            return None
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        path = request.path
        for exempt in self.EXEMPT_PATHS:
            if path.startswith(exempt):
                return None

        from users.models import UserProfile
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile and profile.is_2fa_enabled and not request.session.get('2fa_verified'):
            from django.shortcuts import redirect
            return redirect(f'/users/2fa/verify/?next={path}')

        return None
