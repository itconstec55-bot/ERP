import os
import sys
from pathlib import Path
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG or 'test' in sys.argv:
        # مفتاح مؤقت للتطوير/الاختبار فقط — يُولَّد عشوائياً كل تشغيل
        # (لا يُستخدم أبداً في الإنتاج حيث يجب ضبط DJANGO_SECRET_KEY)
        SECRET_KEY = get_random_secret_key()
    else:
        raise RuntimeError(
            'DJANGO_SECRET_KEY environment variable is required in production. '
            'Set it before starting the server.'
        )

# ---------------------------------------------------------------------------
# ربط الشبكة (Network Binding) — LAN + خارجي
# ---------------------------------------------------------------------------
# عناوين الاستماع تُقرأ من ملف network.conf (INTERNAL_IP / EXTERNAL_IP / PORT)
# لأقصى سهولة، مع إمكانية تجاوزها عبر متغيّرات البيئة DJANGO_BIND_HOSTS /
# DJANGO_BIND_PORT. يُشغَّل كل عنوان كعملية خادم مستقلة (انظر run_multi.py).
# ملاحظة: IP الخارجي العام عادة على الراوتر؛ يُوجَّه عبر المنفذ (انظر التوثيق).
def _read_network_conf():
    cfg = {}
    conf_path = BASE_DIR / 'network.conf'
    if conf_path.exists():
        for raw in conf_path.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            cfg[key.strip()] = val.strip()
    return cfg


_net_cfg = _read_network_conf()
_internal_ip = _net_cfg.get('INTERNAL_IP', '192.168.1.31')
_external_ip = _net_cfg.get('EXTERNAL_IP', '196.218.24.45')
_default_bind = f'{_internal_ip},{_external_ip}'

_bind_hosts = [
    h.strip() for h in os.environ.get('DJANGO_BIND_HOSTS', _default_bind).split(',') if h.strip()
]
# نضيف اللووباك دائماً ليكون الوصول من نفس الجهاز عبر localhost متاحاً دون جدار ناري
_bind_hosts = sorted(set(_bind_hosts) | {'127.0.0.1'})
SERVER_BIND_HOSTS = _bind_hosts
SERVER_BIND_PORT = int(os.environ.get('DJANGO_BIND_PORT', _net_cfg.get('PORT', '8012')))

# المضيفات المسموح بها (Host header) = التطوير الافتراضي + عناوين الربط.
_allowed_extra = {
    h.strip() for h in os.environ.get(
        'DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver'
    ).split(',') if h.strip()
}
_allowed_extra.update(SERVER_BIND_HOSTS)
ALLOWED_HOSTS = sorted(_allowed_extra)

# مصادر موثوقة لـ CSRF عند الوصول عبر عناوين الربط (مع أو بدون HTTPS عبر الوكيل).
CSRF_TRUSTED_ORIGINS = (
    [f'http://{h}' for h in SERVER_BIND_HOSTS]
    + [f'https://{h}' for h in SERVER_BIND_HOSTS]
    + ['http://127.0.0.1', 'http://localhost']
)

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'crispy_forms',
    'crispy_bootstrap5',
    'accounts',
    'purchases',
    'sales',
    'treasury',
    'assets',
    'hr',
    'reports',
    'documents',
    'warehouses',
    'company',
    'ai_analysis',
    'concrete_production',
    'contractors',
    'backups',
    'sync',
    'users',
    'audit',
    'budget',
    'currency',
    'bank_reconciliation',
    'notifications',
    'recurring',
    'credit_notes',
    'cheques',
    'sales_returns',
    'purchase_returns',
    'stock_adjustments',
    'payment_receipts',
    'tax_invoices',
    'purchase_orders',
    'sales_orders',
    'goods_received',
    'requisitions',
    'rfq',
    'sales_quotation',
    'access_control',
    'common',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'api',
    'celery',
    'drf_spectacular',
]

# DRF Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'api.pagination.StandardResultsPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'auth': '20/hour',
    },
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Sync Settings
MACHINE_ID = 'MACHINE-DEFAULT'
MACHINE_NAME = 'الجهاز الرئيسي'
MACHINE_TYPE = 'standalone'  # host, client, standalone

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'accounting_system.middleware.CSPMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'accounting_system.middleware.IdleSessionTimeoutMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounting_system.middleware.SessionTrackingMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'accounting_system.middleware.LoginThrottleMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounting_system.middleware.RequestLoggingMiddleware',
    'accounting_system.middleware.ErrorHandlingMiddleware',
    'audit.middleware.AuditMiddleware',
    'accounting_system.middleware.TwoFactorAuthMiddleware',
]

ROOT_URLCONF = 'accounting_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'company.context_processors.company_context',
                'common.context_processors.user_permissions_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'accounting_system.wsgi.application'

# قاعدة البيانات: SQLite افتراضياً للتطوير، وPostgreSQL للإنتاج/التوسع
# التبديل عبر متغيرات البيئة (لا يغيّر السلوك الحالي على SQLite)
if os.environ.get('DJANGO_DB_ENGINE') == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DJANGO_DB_NAME', 'accounting'),
            'USER': os.environ.get('DJANGO_DB_USER', 'accounting'),
            'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', ''),
            'HOST': os.environ.get('DJANGO_DB_HOST', '127.0.0.1'),
            'PORT': os.environ.get('DJANGO_DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.environ.get('DJANGO_DB_CONN_MAX_AGE', '600')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            # timeout مقبول مباشرة من sqlite3.connect. إعدادات WAL/buszy_timeout
            # تُطبَّق عبر إشارة connection_created (انظر أسفل) لأنها PRAGMA لا تُقبل كـ OPTIONS.
            'OPTIONS': {
                'timeout': 30,
            },
            'CONN_MAX_AGE': 60,
        }
    }

    # تطبيق PRAGMAs على كل اتصال SQLite جديد لتحسين التزامن على الشبكة:
    # WAL يسمح بقرّاء متزامنين مع كاتب واحد، وbusy_timeout يقلّل أخطاء "database is locked".
    from django.db.backends.signals import connection_created
    from django.dispatch import receiver

    @receiver(connection_created)
    def _configure_sqlite(connection, **kwargs):
        if connection.vendor == 'sqlite':
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.execute("PRAGMA synchronous=NORMAL;")

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Logging Configuration
# تأكد من وجود مجلد logs قبل إعداد الـ handlers (تفادياً لفشل RotatingFileHandler)
_LOGS_DIR = BASE_DIR / 'logs'
try:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'request': {
            'format': '{asctime} {levelname} [{module}] {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'accounting.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'request_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'requests.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'request',
            'encoding': 'utf-8',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': False,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['error_file', 'request_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'accounting': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'accounting.request': {
            'handlers': ['request_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# في وضع الإنتاج (DEBUG=False) يخدم whitenoise الملفات الثابتة بلا خادم منفصل
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.StaticFilesStorage'},
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Accounting Settings
COMPANY_NAME = 'شركة تواريدات للتجارة'
COMPANY_ADDRESS = 'القاهرة، مصر'
COMPANY_PHONE = '01000000000'
COMPANY_TAX_NUMBER = '123456789'
VAT_RATE = 14  # 14% VAT in Egypt

# Fiscal Year
FISCAL_YEAR_START = '01-01'
FISCAL_YEAR_END = '12-31'

# Login URLs
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Error Pages
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'accounting_system.views.custom_server_error'

# Session Settings
SESSION_COOKIE_AGE = 86400 * 7  # 7 days
# False (افتراضي Django): تُحفظ الجلسة عند تعديلها فقط — يقلّل كتابات قاعدة البيانات لكل طلب
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True  # منع الوصول للكوكيز عبر JavaScript (حماية XSS)
CSRF_COOKIE_HTTPONLY = True     # منع الوصول لـ CSRF cookie عبر JavaScript

# Security Settings (for production)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 'yes')
    # الكوكيز آمنة افتراضياً في الإنتاج — يمكن تعطيلها عبر متغيرات البيئة
    SESSION_COOKIE_SECURE = os.environ.get(
        'DJANGO_SESSION_COOKIE_SECURE', 'True'
    ).lower() in ('true', '1', 'yes')
    CSRF_COOKIE_SECURE = os.environ.get(
        'DJANGO_CSRF_COOKIE_SECURE', 'True'
    ).lower() in ('true', '1', 'yes')
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
        'DJANGO_HSTS_SUBDOMAINS', 'True'
    ).lower() in ('true', '1', 'yes')
    SECURE_HSTS_PRELOAD = SECURE_HSTS_INCLUDE_SUBDOMAINS

# ---------------------------------------------------------------------------
# Email Settings (Email Configuration)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('DJANGO_EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('DJANGO_EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('DJANGO_EMAIL_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('DJANGO_EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_DEFAULT_FROM_EMAIL', 'نظام المحاسبة <noreply@accounting.local>')
ALLOWED_EMAIL_DOMAIN = os.environ.get('DJANGO_ALLOWED_EMAIL_DOMAIN', None)

# ---------------------------------------------------------------------------
# 2FA Settings (المصادقة الثنائية)
# ---------------------------------------------------------------------------
TOTP_ISSUER_NAME = 'نظام المحاسبة'
REQUIRE_2FA = os.environ.get('DJANGO_REQUIRE_2FA', 'False').lower() in ('true', '1', 'yes')

# ---------------------------------------------------------------------------
# Credit Limit Settings (حد الائتمان)
# ---------------------------------------------------------------------------
CREDIT_LIMIT_HARD_BLOCK = os.environ.get('DJANGO_CREDIT_LIMIT_HARD', 'False').lower() in ('true', '1', 'yes')
CREDIT_LIMIT_WARNING_ONLY = not CREDIT_LIMIT_HARD_BLOCK

# WhatsApp Business API Configuration
WHATSAPP_APP_ID = os.environ.get('WHATSAPP_APP_ID')
WHATSAPP_APP_SECRET = os.environ.get('WHATSAPP_APP_SECRET')
WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID')
WHATSAPP_API_TOKEN = os.environ.get('WHATSAPP_API_TOKEN')
WHATSAPP_API_BASE_URL = "https://graph.facebook.com/v18.0"
WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.environ.get('WHATSAPP_WEBHOOK_VERIFY_TOKEN')

WHATSAPP_RATE_LIMITS = {
    "messages_per_second": 80,
    "messages_per_minute": 1000,
    "messages_per_hour": 50000,
    "messages_per_day": 1000000,
}

# Jazzmin Settings
JAZZMIN_SETTINGS = {
    "site_title": "نظام المحاسبة",
    "site_header": "نظام المحاسبة - شركة تواريدات",
    "site_brand": "تواريدات",
    "welcome_sign": "مرحباً بك في لوحة التحكم",
    "copyright": "شركة تواريدات",
    "site_logo_classes": "img-circle",
    "show_ui_title": True,
    "topmenu_links": [
        {"name": "الرئيسية", "url": "admin:index", "icon": "fas fa-home"},
        {"name": "لوحة التحكم", "url": "/", "icon": "fas fa-tachometer-alt", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": ["ai_analysis"],
    "hide_models": [],
    "order_with_respect_to": [
        "auth",
        "accounts",
        "purchases",
        "sales",
        "treasury",
        "assets",
        "hr",
        "reports",
        "documents",
        "warehouses",
        "company",
        "notifications",
        "backups",
        "audit",
        "sync",
        "ai_analysis",
        "concrete_production",
        "contractors",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.Group": "fas fa-users",
        "auth.User": "fas fa-user-circle",
        "accounts.account": "fas fa-sitemap",
        "accounts.accounttype": "fas fa-layer-group",
        "accounts.journalentry": "fas fa-book",
        "accounts.journalentryline": "fas fa-book-open",
        "purchases.supplier": "fas fa-truck",
        "purchases.product": "fas fa-box",
        "purchases.productcategory": "fas fa-tags",
        "purchases.unitofmeasure": "fas fa-ruler",
        "purchases.purchaseinvoice": "fas fa-shopping-cart",
        "purchases.purchaseinvoiceline": "fas fa-cart-plus",
        "sales.customer": "fas fa-user-tie",
        "sales.salesinvoice": "fas fa-cash-register",
        "sales.salesinvoiceline": "fas fa-receipt",
        "treasury.bank": "fas fa-university",
        "treasury.safe": "fas fa-lock",
        "treasury.banktransaction": "fas fa-exchange-alt",
        "treasury.safetransaction": "fas fa-money-bill-wave",
        "assets.asset": "fas fa-building",
        "assets.assetcategory": "fas fa-tags",
        "assets.depreciationentry": "fas fa-chart-line",
        "hr.employee": "fas fa-id-badge",
        "hr.department": "fas fa-sitemap",
        "hr.salary": "fas fa-money-check-alt",
        "hr.attendance": "fas fa-calendar-check",
        "documents.document": "fas fa-file-alt",
        "documents.documenttype": "fas fa-folder",
        "documents.documenttemplate": "fas fa-file-medical-alt",
        "documents.documentflow": "fas fa-exchange-alt",
        "documents.documentattachment": "fas fa-paperclip",
        "warehouses.warehouse": "fas fa-warehouse",
        "warehouses.warehouseproduct": "fas fa-boxes",
        "warehouses.stockmovement": "fas fa-exchange-alt",
        "company.company": "fas fa-building",
        "company.companybranch": "fas fa-code-branch",
        "notifications.notificationcategory": "fas fa-tags",
        "notifications.notificationtemplate": "fas fa-file-alt",
        "notifications.notificationlog": "fas fa-bell",
        "backups.backup": "fas fa-cloud-upload-alt",
        "backups.backupsettings": "fas fa-cog",
        "audit.auditlog": "fas fa-history",
        "sync.machineinfo": "fas fa-desktop",
        "sync.synclog": "fas fa-sync",
        "sync.syncsettings": "fas fa-cogs",
        "concrete_production.concretemixdesign": "fas fa-flask",
        "concrete_production.mixcomponent": "fas fa-puzzle-piece",
        "concrete_production.customerrequest": "fas fa-file-alt",
        "concrete_production.productionorder": "fas fa-hard-hat",
        "concrete_production.productionbatch": "fas fa-industry",
        "concrete_production.deliveryschedule": "fas fa-calendar-check",
        "concrete_production.truck": "fas fa-truck",
        "concrete_production.productioncost": "fas fa-dollar-sign",
        "contractors.contractor": "fas fa-hard-hat",
        "contractors.contract": "fas fa-file-contract",
        "contractors.contractitem": "fas fa-list",
        "contractors.interimcertificate": "fas fa-file-alt",
        "contractors.certificateitem": "fas fa-list-alt",
        "contractors.contractorpayment": "fas fa-money-bill-wave",
    },
    "default_icon_parents": "fas fa-folder-open",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": "css/admin_custom.css",
    "custom_js": None,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "vertical_tabs",
        "accounts.account": "horizontal_tabs",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": False,
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "default_theme_mode": "dark",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# ---------------------------------------------------------------------------
# OpenAPI / Swagger (drf-spectacular)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'نظام المحاسبة المتكامل - API',
    'DESCRIPTION': 'واجهة برمجة تطبيقات لنظام المحاسبة المتكامل',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {'email': 'admin@example.com'},
    'LICENSE': {'name': 'Proprietary'},
}

# ---------------------------------------------------------------------------
# Celery (المهام غير المتزامنة)
# ---------------------------------------------------------------------------
# افتراضياً CELERY_TASK_ALWAYS_EAGER=True => تُنفَّذ المهام متزامنياً بلا وسيط،
# فلا حاجة لخادم Redis/وسيط الآن. عند توفير وسيط (DJANGO_CELERY_BROKER) اضبط
# DJANGO_CELERY_EAGER=False لتصبح المهام غير متزامنة تلقائياً (تشغيل worker).
CELERY_BROKER_URL = os.environ.get('DJANGO_CELERY_BROKER', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('DJANGO_CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_TASK_ALWAYS_EAGER = os.environ.get('DJANGO_CELERY_EAGER', 'True').lower() in ('true', '1', 'yes')
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_WORKER_CONCURRENCY = int(os.environ.get('DJANGO_CELERY_CONCURRENCY', '4'))

# ── Celery Beat Schedule ──
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'execute-recurring-journals-daily': {
        'task': 'recurring.execute_due_journals',
        'schedule': crontab(hour=1, minute=0),  # 1 AM daily
    },
    'cleanup-old-sessions-daily': {
        'task': 'django.contrib.sessions.tasks.clear_sessions',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
}

# ---------------------------------------------------------------------------
# Cache Settings
# ---------------------------------------------------------------------------
# في الإنتاج، يُفضل استخدام Redis كخزّان مؤقت مشترك لضمان عمل
# Rate Limiting بشكل صحيح عبر جميع عمليات Gunicorn.
if os.environ.get('DJANGO_CACHE_BACKEND') == 'redis':
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.environ.get('DJANGO_CACHE_URL', 'redis://127.0.0.1:6379/2'),
            'TIMEOUT': 300,
            'OPTIONS': {
                'db': int(os.environ.get('DJANGO_CACHE_DB', '2')),
            }
        }
    }
else:
    # الافتراضي: LocMemCache (محلي لكل عملية - لا يعمل بشكل مشترك)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
            'TIMEOUT': 300,
        }
    }
