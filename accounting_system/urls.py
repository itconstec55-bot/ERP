from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.views.decorators.http import require_GET
from reports.views import dashboard_view
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from accounting_system import views as accounting_views


@require_GET
def health_api(request):
    """API health check endpoint for monitoring."""
    checks = {"status": "ok"}
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        checks["status"] = "degraded"

    import shutil
    usage = shutil.disk_usage(str(settings.BASE_DIR))
    checks["disk_free_mb"] = usage.free // (1024 * 1024)

    status_code = 200 if checks["status"] == "ok" else 503
    return JsonResponse(checks, status=status_code)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_api, name='health_api'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/accounts/login/'), name='logout'),
    # Password Reset (Forgot Password)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/password-reset-complete/',
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('', dashboard_view, name='dashboard'),
    path('accounts/', include('accounts.urls')),
    path('purchases/', include('purchases.urls')),
    path('sales/', include('sales.urls')),
    path('treasury/', include('treasury.urls')),
    path('assets/', include('assets.urls')),
    path('hr/', include('hr.urls')),
    path('reports/', include('reports.urls')),
    path('documents/', include('documents.urls')),
    path('warehouses/', include('warehouses.urls')),
    path('company/', include('company.urls')),
    path('ai/', include('ai_analysis.urls')),
    path('concrete/', include('concrete_production.urls')),
    path('contractors/', include('contractors.urls')),
    path('backups/', include('backups.urls')),
    path('sync/', include('sync.urls')),
    path('users/', include('users.urls')),
    path('audit/', include('audit.urls')),
    path('budget/', include('budget.urls')),
    path('currency/', include('currency.urls')),
    path('bank-reconciliation/', include('bank_reconciliation.urls')),
    path('notifications/', include('notifications.urls')),
    path('common/', include('common.urls')),
    path('recurring/', include('recurring.urls')),
    path('credit-notes/', include('credit_notes.urls')),
    path('cheques/', include('cheques.urls')),
    path('sales-returns/', include('sales_returns.urls')),
    path('purchase-returns/', include('purchase_returns.urls')),
    path('stock-adjustments/', include('stock_adjustments.urls')),
    path('payment-receipts/', include('payment_receipts.urls')),
    path('tax-invoices/', include('tax_invoices.urls')),
    path('purchase-orders/', include('purchase_orders.urls')),
    path('sales-orders/', include('sales_orders.urls')),
    path('goods-received/', include('goods_received.urls')),
    path('requisitions/', include('requisitions.urls')),
    path('rfq/', include('rfq.urls')),
    path('quotations/', include('sales_quotation.urls')),
    path('access-control/', include('access_control.urls')),
    path('api/v1/', include('api.urls')),
    # OpenAPI / Swagger
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    # Monitoring Dashboard
    path('monitoring/', accounting_views.monitoring_dashboard, name='monitoring_dashboard'),
    path('monitoring/api/metrics/', accounting_views.monitoring_api_metrics, name='monitoring_api_metrics'),
    path('monitoring/api/history/', accounting_views.monitoring_api_history, name='monitoring_api_history'),
    path('monitoring/api/status/', accounting_views.monitoring_api_status, name='monitoring_api_status'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # الإنتاج: جونيكورن لا يخدم media تلقائياً، نخدمها عبر Django static serve
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
