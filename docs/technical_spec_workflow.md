# وثيقة التعريف التقني لحركة العمل
## نظام المحاسبة المتكامل — شركة تواريدات للتجارة

> وثيقة معمارية تشغيلية تشرح هيكل المشروع، حركة العمل، آليات ربط الشاشات،
> المكتبات المستخدمة، وتدفق البيانات بين الواجهة والخلفية، مع اعتبارات أمنية وأدائية.

---

## ١. نظرة عامة على الهيكل وبيئة التطوير

### 1.1 هندسة النظام
النظام تطبيق ويب من نمط **Server-Rendered** مبني على إطار العمل Django (نمط
MTV: Model–Template–View). لا يوجد تطبيق صفحة واحدة (SPA) منفصل للواجهة؛ كل
شاشة تُولَّد على الخادم وترسل كـ HTML. لذلك تُترجَم مفاهيم "Props / State"
إلى ما يلي في سياق Django:

| المفهوم في SPA | المكافئ في هذا النظام |
|---|---|
| Props | متغيّرات سياق القالب (Context) المُمرَّرة عبر `render()` |
| State (عميل) | حالة بسيطة بـ JS (طيّ القوائم، جلب JSON) |
| State (خادم) | قاعدة البيانات (Models)، الجلسة (Session)، الذاكرة المخبّأة (Cache) |
| Source of Truth للتنقّل | عنوان URL (المسار + سلسلة الاستعلام) |

### 1.2 بنية المشروع (هيكل الحزم)
```
accounting_system/          # إعدادات المشروع
├── settings.py             # الإعدادات (DB، ALLOWED_HOSTS، CELERY، الربط الشبكي)
├── urls.py                 # الموجِّه الجذر (يشمل التطبيقات الفرعية)
├── celery.py               # تهيئة Celery
└── middleware.py           # LoginThrottleMiddleware (حدّ محاولات الدخول)
accounts/ sales/ purchases/ treasury/ assets/ hr/ reports/ documents/
warehouses/ company/ ai_analysis/ concrete_production/ contractors/ backups/
sync/ users/ audit/ budget/ currency/ bank-reconciliation/ notifications/
common/ recurring/ credit_notes/ cheques/ sales_returns/ purchase_returns/
stock_adjustments/ payment_receipts/   # تطبيقات Django (كل تطبيق: models, views, urls, templates)
common/                     # صلاحيات، معالجات سياق، نماذج مشتركة
templates/base/             # القالب الأساسي (sidebar / topbar)
static/ staticfiles/ media/
requirements.txt  network.conf  run_multi.py  run.bat
```
كل "تطبيق" (App) يحتوي على: `models.py`، `views.py`، `urls.py`، مجلد `templates/<app>/`.

### 1.3 بيئة التطوير والتشغيل
- **اللغة:** Python 3.15 (المفسر: `D:\python 3.15\python.exe`)
- **الإطار:** Django 4.2.30 (إصدار LTS)
- **قاعدة البيانات:** SQLite افتراضياً، قابلة للتبديل إلى PostgreSQL عبر
  `DJANGO_DB_ENGINE=postgres` + بيانات الاتصال.
- **الواجهة:** Bootstrap 5.3 + خط Cairo + Font Awesome 6.4 + Jazzmin (واجهة الإدارة).
- **التشغيل:** `run_multi.py` (ربط متعدد العناوين) للتطوير، أو
  Nginx + Gunicorn في الإنتاج (انظر `deploy/`).
- **المهام غير المتزامنة:** Celery 5.6.3 (وضع `eager` افتراضياً بلا وسيط).

---

## ٢. حركة العمل (Workflow)

### 2.1 التدفق العام — من الدخول حتى إتمام العملية الأساسية
1. **المصادقة:** يصل المستخدم إلى `/accounts/login/`؛ يعالج Django المصادقة،
   ويُنشئ جلسة، ويوجِّهه (`?next=`) إلى لوحة التحكم `/`.
2. **لوحة التحكم:** تعرض مؤشرات (عبر `dashboard_view` + تقارير)؛ التنقّل
   عبر الشريط الجانبي المبني على الصلاحيات.
3. **العملية الأساسية — دورة فاتورة مبيعات الخرسانة:**
   - أ. `concrete_production:customer_request_create` ← طلب عميل.
   - ب. `concrete_production:production_order_create` ← أمر إنتاج مرتبط بالطلب.
   - ج. تسجيل الدفعات (`production_batch`) والتسليمات (`delivery_schedule`).
   - د. عند إتمام أمر الإنتاج (`status='completed'`) تُنشأ **فاتورة مبيعات
     تلقائياً** مرتبطة به (`SalesInvoice.production_order`) داخل
     `transaction.atomic`، ويُرحَّل قيدها.
   - هـ. `sales:sales_invoice_post` ← ترحيل القيد المحاسبي (يُحدِّث أرصدة
     الحسابات ذرّياً عبر `select_for_update`).
   - و. `sales:sales_invoice_print` / `whatsapp` ← طباعة/إرسال.
4. **التقارير:** تُجمَّع في `reports` (مخزَّنة عبر `@cache_page`).

### 2.2 آلية الربط بين الخطوات
كل خطوة تنتهي بـ `redirect()` إلى الشاشة التالية باستخدام `reverse()` بمعرِّف
المسار وتمرير المفتاح الأساسي (`pk`) في المسار — مما يحافظ على **عنوان URL
كـ Single Source of Truth** لحالة التنقّل:

```python
# concrete_production/views.py — بعد الجدولة
return redirect('concrete_production:production_order_detail', pk=order.pk)
```

---

## ٣. آليات ربط الشاشات (Screen Navigation)

### 3.1 التوجيه الداخلي (Routing)
- الموجِّه الجذر `accounting_system/urls.py` يضمّ التطبيقات عبر `include()`
  مع `app_name` (namespace) يمنع تعارض الأسماء.
- كل تطبيق له `urls.py` يعرّف الأنماط ومُحوِّلات المسار (Path Converters):

```python
# sales/urls.py
app_name = 'sales'
urlpatterns = [
    path('invoices/', views.sales_invoice_list, name='invoice_list'),
    path('invoices/create/', views.sales_invoice_create, name='invoice_create'),
    path('invoices/<uuid:pk>/', views.sales_invoice_detail, name='invoice_detail'),
    path('invoices/<uuid:pk>/post/', views.sales_invoice_post, name='invoice_post'),
]
```
`<uuid:pk>` يستخرج المفتاح الأساسي من URL ويمرّره للدالة view.

### 3.2 التنقّل في القوالب (Template Navigation)
القوالب تستخدم الوسم `{% url %}` بمعرِّف المسار والـ namespace (لا روابط ثابتة):

```html
<a href="{% url 'sales:invoice_create' %}">فاتورة بيع</a>
```
إبراز الشاشة النشطة بمقارنة `request.resolver_match.url_name`:
```html
<a href="{% url 'dashboard' %}"
   class="{% if request.resolver_match.url_name == 'dashboard' %}active{% endif %}">
   لوحة التحكم
</a>
```
تمرير بيانات بين الشاشات عبر **سلسلة الاستعلام (QueryString)** — مثال من
الشريط الجانبي:
```html
<a href="{% url 'payment_receipts:create' %}?type=receipt">سند قبض</a>
```
وتُقرأ في الـ View عبر `request.GET.get('type')`.

### 3.3 "الوسائط والحالة" (Props / State) في سياق Django
- **Props** = سياق القالب:
  ```python
  return render(request, 'concrete_production/production_order_detail.html', {
      'order': order, 'batches': batches, 'deliveries': deliveries, 'costs': costs,
  })
  ```
- **State — قاعدة البيانات (ربط الكيانات عبر الشاشات):** العلاقات (FK) تربط
  الشاشات. مثال ربط فاتورة بأمر إنتاج:
  ```python
  # sales/models.py
  class SalesInvoice(models.Model):
      production_order = models.ForeignKey(
          'concrete_production.ProductionOrder', null=True, blank=True,
          on_delete=models.SET_NULL, related_name='sales_invoice')
  ```
  ويُعرض في قالب تفاصيل الأمر: `{{ order.sales_invoice.invoice_number }}`.
- **State — الجلسة (Session):** بيانات الفرع/المستخدم.
- **State — معالجات السياق (Context Processors):** تُحقن تلقائياً في كل قالب:
  ```python
  # common/context_processors.py
  def user_permissions_context(request):
      if request.user.is_superuser:
          perms = {'all'}
      else:
          perms = set(request.user.get_all_permissions())
      return {'user_perms': perms, 'is_superuser': request.user.is_superuser}
  ```
  وتُستخدم لإظهار/إخفاء روابط الشريط الجانبي حسب الصلاحية:
  ```html
  {% if "all" in user_perms or "sales.add_salesinvoice" in user_perms %}
    <a href="{% url 'sales:invoice_create' %}">فاتورة بيع</a>
  {% endif %}
  ```
- **State — الرسائل (Messages Framework):** تمرير إشعارات لمرة واحدة بين
  الطلبات (`messages.success(request, '...')`).
- **State — العميل (JS):** الحد الأدنى. مثال جلب بيانات جزئية بأمان:
  ```javascript
  const data = JSON.parse(document.getElementById('chart-data').textContent);
  ```
  حيث يُحقن الـ JSON عبر `{{ chart_data_json|json_script:"chart-data" }}`
  (تفادي حقن XSS بدل `|safe`).

---

## ٤. البرامج والمكتبات (الإصدارات والسبب)

| المكتبة | الإصدار | السبب / دورها |
|---|---|---|
| Python | 3.15 | مفسر التشغيل |
| Django | 4.2.30 (LTS) | إطار العمل؛ استقرار طويل الأمد ودعم PostgreSQL |
| psycopg2-binary | ≥2.9 | توصيل PostgreSQL عند التبديل من SQLite |
| django-crispy-forms | 2.5 | تقديم النماذج بأناقة مع Bootstrap |
| crispy-bootstrap5 | 2026.3 | دعم Bootstrap 5 لـ crispy-forms |
| django-jazzmin | ≥2.6 | واجهة إدارة Django محسّنة (تدعم RTL) |
| reportlab | ≥4.0 | توليد تقارير/فواتير PDF |
| openpyxl | ≥3.1 | استيراد/تصدير ملفات Excel |
| python-dateutil | ≥2.8 | معالجة التواريخ في التقارير |
| faker | ≥20.0 | بيانات وهمية للاختبار (`seed_dummy_data`) |
| Celery | 5.6.3 | المهام غير المتزامنة (إعادة حساب الأرصدة) |
| redis (py) | 8.0.1 | وسيط/مخزن نتائج Celery (اختياري) |
| Bootstrap 5.3 / Font Awesome 6.4 / خط Cairo | — | الواجهة العربية RTL |

---

## ٥. تدفق البيانات (Frontend ↔ Backend)

### 5.1 المخطط النصي والبصري لتدفق البيانات
> مخطط بصري (صورة + PDF) متاح في: `docs/diagrams/data_flow.svg` و
> `docs/diagrams/data_flow.pdf` — ويبيّن نفس التدفق أدناه بصرياً.
```
[المتصفح]
   │  GET /sales/invoices/<pk>/   (أو POST نموذج + csrfmiddlewaretoken)
   ▼
[الخادم: Nginx ← Gunicorn / runserver]
   │      (الإنتاج: Nginx يستمع على العناوين ويوكِّل إلى 127.0.0.1:8012)
   ▼
[Middleware]  →  LoginThrottleMiddleware, SessionMiddleware, CsrfViewMiddleware
   ▼
[URL Resolver]  →  يطابق المسار ويستدعي الـ View بمعاملات (pk)
   ▼
[View]  →  فحص الصلاحية (permission_required_or_login)
   │         →  استعلام ORM (select_related / prefetch_related)
   │         ↓
   ▼      [Database: SQLite / PostgreSQL]
[Context]  ←  يبني قاموس السياق (الكائنات + معالجات السياق)
   ▼
[Template]  ←  تصيير HTML (DTL) + موارد static
   ▼
[HTTP Response]  →  يعرض المتصفح الشاشة
```
للبيانات الجزئية (JSON APIs) يُعيد الـ View `JsonResponse` ويستهلكه المتصفح
بـ `fetch`:
```python
# concrete_production/views.py
def api_silo_stock(request):
    silos = Silo.objects.filter(is_active=True)
    data = [{'id': s.id, 'code': s.code, 'stock': float(s.current_stock_tons)}
            for s in silos]
    return JsonResponse({'silos': data})
```
```javascript
fetch('/concrete/api/silo-stock/').then(r => r.json()).then(d => renderChart(d.silos));
```

### 5.2 اعتبارات أمنية
- **CSRF:** `CsrfViewMiddleware` + `{% csrf_token %}` في كل نموذج POST؛ و
  `CSRF_TRUSTED_ORIGINS` مُشتق من عناوين الربط.
- **الصلاحيات:** `@permission_required_or_login` + فحص على مستوى الكائن
  (`has_object_permission`) لمنع وصول الفروع الأخرى.
- **ALLOWED_HOSTS:** مُشتق من عناوين الربط (`SERVER_BIND_HOSTS`).
- **SECRET_KEY:** إلزامي في الإنتاج (يُرفع الخطأ إن غاب).
- **حدّ الدخول:** `LoginThrottleMiddleware` (10 محاولة/5 دقائق لكل IP → 429).
- **حقن JSON:** `json_script` بدل `|safe`.
- **كوكيز آمنة** (Secure/HSTS) عند تفعيل SSL عبر `DJANGO_SECURE_SSL_REDIRECT`.

### 5.3 اعتبارات أدائية
- **تجنّب N+1:** `select_related`/`prefetch_related` — مثال:
  `ProductionOrder.objects.select_related('customer_request__customer','mix_design')`.
- **ترقيم القوائم:** `Paginator(queryset, 25)` وتغيير الصفحة عبر `?page=`.
- **تخزين مؤقت:** `@cache_page(300)` + `@vary_on_cookie` للشاشات الثقيلة.
- **مهام ثقيلة:** إعادة حساب الأرصدة عبر مهمة Celery (`recalc_balances_task`)
  بدل التزامن.
- **سلامة التزامن:** تحديثات المخزون الحرجة داخل `transaction.atomic()` +
  `select_for_update()` (مثال: `SiloTransaction.save`، `JournalEntry.post`)
  لتفادي سباق التحديثات (Lost Update).

---

*الوثيقة مبنية على فحص مباشر لشفرة المشروع (settings.py، urls.py، views،
templates/base، context_processors، requirements.txt).*

---

## ٦. جدول صلاحيات الشاشات (Permission Matrix)
> الجدول التالي استُخرج آلياً من مزخرفات (decorators) دوال العرض في كل التطبيقات
> (يغطي 337 شاشة/دالة). الرمز — (عام/بلا قيد) يعني أنه لا يوجد مزخرف صلاحية
> (بعضها محمي بـ login_required فقط، وبعض نقاط API محمي بمفتاح API بدل صلاحية Django).
> النسخة الكاملة محفوظة أيضاً في docs/permissions_matrix.md.
| Ø§Ù„ØªØ·Ø¨ÙŠÙ‚ (App) | Ø§Ù„Ø´Ø§Ø´Ø©/Ø§Ù„Ø¯Ø§Ù„Ø© (View) | Ù…Ø³ØªÙˆÙ‰ Ø§Ù„ÙˆØµÙˆÙ„ / Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ© Ø§Ù„Ù…Ø·Ù„ÙˆØ¨Ø© |
|---|---|---|
| `accounts` | `account_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'accounts.view_account' |
| `accounts` | `account_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `account_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `account_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `account_statement` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `journal_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'accounts.view_journalentry' |
| `accounts` | `journal_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'accounts.add_journalentry' |
| `accounts` | `journal_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `journal_post` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `trial_balance` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `chart_of_accounts` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `export_accounts` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `import_accounts` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `export_journal` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `accounts` | `fiscal_year_close` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `ai_analysis` | `dashboard` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `ai_analysis` | `analyze_error` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `ai_analysis` | `auto_detect` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `ai_analysis` | `error_history` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `ai_analysis` | `error_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `ai_analysis` | `apply_solution` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `ai_analysis` | `api_detect_errors` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `ai_analysis` | `api_analyze_error` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `ai_analysis` | `api_error_stats` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `asset_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `asset_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `asset_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `asset_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `depreciation_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `asset_category_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `asset_category_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `export_assets` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `assets` | `import_assets` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `audit` | `audit_log_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `backups` | `_ensure_backup_dir` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `backups` | `_format_size` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `backups` | `_safe_extract_zip` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `backups` | `backup_dashboard` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `backups` | `create_backup` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `backups` | `download_backup` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `backups` | `delete_backup` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `backups` | `restore_backup` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `backups` | `export_json` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `backups` | `import_json` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `backups` | `backup_settings_view` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `reconciliation_dashboard` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `session_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `session_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `item_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `item_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `item_match` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `import_csv` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `auto_match` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `bank_reconciliation` | `item_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `budget` | `cost_center_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `budget` | `cost_center_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `budget` | `budget_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `budget` | `budget_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `cheques` | `cheque_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `cheques` | `cheque_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `cheques` | `cheque_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `cheques` | `cheque_update_status` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `cheques` | `cheque_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `cheques` | `cheque_dashboard` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `common` | `whatsapp_webhook` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `company_settings` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `company` | `branch_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `company` | `branch_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `company` | `branch_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `company` | `admin_settings_dashboard` | ØµÙ„Ø§Ø­ÙŠØ©: 'accounts.change_accounttype', raise_exception=True |
| `company` | `account_type_create` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `account_type_update` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `account_type_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `product_create` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `product_update` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `product_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `category_create` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `category_update` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `category_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `unit_create` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `unit_update` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `company` | `unit_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `credit_notes` | `credit_note_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `credit_notes` | `credit_note_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `credit_notes` | `credit_note_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `credit_notes` | `credit_note_post` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `credit_notes` | `credit_note_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `currency` | `currency_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `currency` | `currency_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `currency` | `currency_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `currency` | `exchange_rate_history` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_type_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_type_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_type_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_template_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_template_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_template_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_action` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `documents` | `document_add_attachment` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `hr` | `employee_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.view_employee' |
| `hr` | `employee_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.add_employee' |
| `hr` | `employee_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.view_employee' |
| `hr` | `employee_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.change_employee' |
| `hr` | `attendance_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.view_attendance' |
| `hr` | `attendance_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.add_attendance' |
| `hr` | `salary_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.view_salary' |
| `hr` | `salary_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.add_salary' |
| `hr` | `salary_post` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `hr` | `department_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.view_department' |
| `hr` | `department_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.add_department' |
| `hr` | `export_employees` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.view_employee' |
| `hr` | `export_salaries` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.export_salary' |
| `hr` | `import_employees` | ØµÙ„Ø§Ø­ÙŠØ©: 'hr.add_employee' |
| `notifications` | `notification_dashboard` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `notifications` | `template_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `notifications` | `template_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `notifications` | `send_test_notification` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `payment_receipts` | `receipt_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.view_bank' |
| `payment_receipts` | `receipt_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `payment_receipts` | `receipt_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `payment_receipts` | `receipt_post` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `payment_receipts` | `receipt_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `payment_receipts` | `receipt_print` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `payment_receipts` | `get_customer_invoices` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `payment_receipts` | `get_supplier_invoices` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `supplier_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'purchases.view_supplier' |
| `purchases` | `supplier_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'purchases.add_supplier' |
| `purchases` | `supplier_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'purchases.view_supplier' |
| `purchases` | `supplier_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'purchases.change_supplier' |
| `purchases` | `product_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `product_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `product_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `catalog_settings` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `purchase_invoice_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `purchase_invoice_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `purchase_invoice_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `purchase_invoice_post` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `purchases` | `purchase_invoice_print` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `purchase_invoice_whatsapp` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `purchases` | `supplier_statement_whatsapp` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `purchases` | `export_suppliers` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `import_suppliers` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `export_products` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `import_products` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `product_barcode_print` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `product_barcode_batch` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchases` | `product_price_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchase_returns` | `purchase_return_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'purchases.view_purchaseinvoice' |
| `purchase_returns` | `purchase_return_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchase_returns` | `purchase_return_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `purchase_returns` | `purchase_return_post` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `purchase_returns` | `purchase_return_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `recurring` | `recurring_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `recurring` | `recurring_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `recurring` | `recurring_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `recurring` | `recurring_execute` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `recurring` | `recurring_toggle` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `recurring` | `recurring_delete` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `recurring` | `_save_lines` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_safe_parse_date` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_validate_date_range` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_get_date_range` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `dashboard_view` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `financial_dashboard` | ØµÙ„Ø§Ø­ÙŠØ©: 'reports.view_reporttemplate' |
| `reports` | `_age_bucket` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `workflow_tracker` | ØµÙ„Ø§Ø­ÙŠØ©: 'reports.view_reporttemplate' |
| `reports` | `report_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `income_statement` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `balance_sheet` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `trial_balance_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `vat_return` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `withholding_tax_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `supplier_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `supplier_detail_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `customer_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `customer_detail_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `profit_margin_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `asset_schedule` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `payroll_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `export_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `_export_simple_xlsx` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `__init__` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `__getattr__` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_daily_sales` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_daily_purchases` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_ar_aging` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_ap_aging` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_income_statement` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_balance_sheet` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_vat_return` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_payroll` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_inventory` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_profit_margin` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_withholding_tax` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_supplier_report` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_customer_report` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_customer_statement` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_supplier_statement` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_trial_balance` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_asset_schedule` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `_export_cash_flow` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `reports` | `ar_aging_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `ap_aging_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `inventory_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `customer_statement` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `supplier_statement` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `daily_sales_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `daily_purchases_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `reports` | `cash_flow_report` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sales` | `customer_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'sales.view_customer' |
| `sales` | `customer_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'sales.add_customer' |
| `sales` | `customer_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'sales.view_customer' |
| `sales` | `customer_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'sales.change_customer' |
| `sales` | `sales_invoice_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'sales.view_salesinvoice' |
| `sales` | `sales_invoice_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'sales.add_salesinvoice' |
| `sales` | `sales_invoice_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sales` | `sales_invoice_post` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `sales` | `sales_invoice_print` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sales` | `sales_invoice_whatsapp` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `sales` | `customer_statement_whatsapp` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `sales` | `export_customers` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sales` | `import_customers` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sales_returns` | `sales_return_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'sales.view_salesinvoice' |
| `sales_returns` | `sales_return_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sales_returns` | `sales_return_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sales_returns` | `sales_return_post` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `sales_returns` | `sales_return_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `stock_adjustments` | `adjustment_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `stock_adjustments` | `adjustment_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `stock_adjustments` | `adjustment_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `stock_adjustments` | `adjustment_approve` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `stock_adjustments` | `adjustment_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `sync` | `_get_or_create_machine` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `sync` | `_verify_api_key` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `sync` | `sync_dashboard` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sync` | `sync_settings_view` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sync` | `test_connection` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sync` | `manual_sync` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sync` | `sync_log_detail` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `sync` | `api_push` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `sync` | `api_pull` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `sync` | `api_status` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `sync` | `api_recalculate` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_http_methods |
| `treasury` | `bank_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.view_bank' |
| `treasury` | `bank_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.add_bank' |
| `treasury` | `bank_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.view_bank' |
| `treasury` | `bank_transaction_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.add_banktransaction' |
| `treasury` | `safe_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.view_safe' |
| `treasury` | `safe_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.add_safe' |
| `treasury` | `safe_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.view_safe' |
| `treasury` | `safe_transaction_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.add_safetransaction' |
| `treasury` | `export_banks` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.view_bank' |
| `treasury` | `export_safes` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.view_safe' |
| `treasury` | `import_banks` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.add_bank' |
| `treasury` | `import_safes` | ØµÙ„Ø§Ø­ÙŠØ©: 'treasury.add_safe' |
| `users` | `clean_password2` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `users` | `save` | â€” (Ø¹Ø§Ù…/Ø¨Ù„Ø§ Ù‚ÙŠØ¯) |
| `users` | `user_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `users` | `user_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `users` | `user_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `users` | `user_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `users` | `group_list` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `users` | `group_create` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `users` | `group_edit` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `users` | `group_delete` | Ù‚ÙŠØ¯ Ø·Ø±ÙŠÙ‚Ø© HTTP: require_POST |
| `users` | `change_password` | Ø¯Ø®ÙˆÙ„ ÙÙ‚Ø· (Ù…ØµØ§Ø¯Ù‚Ø©) |
| `warehouses` | `warehouse_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'warehouses.view_warehouse' |
| `warehouses` | `warehouse_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'warehouses.add_warehouse' |
| `warehouses` | `warehouse_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'warehouses.change_warehouse' |
| `warehouses` | `warehouse_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'warehouses.view_warehouse' |
| `warehouses` | `warehouse_product_add` | ØµÙ„Ø§Ø­ÙŠØ©: 'warehouses.add_warehouseproduct' |
| `warehouses` | `movement_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'warehouses.view_stockmovement' |
| `warehouses` | `movement_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'warehouses.add_stockmovement' |
| `warehouses` | `movement_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'warehouses.view_stockmovement' |
| `concrete_production` | `dashboard` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_concretemixdesign' |
| `concrete_production` | `mix_design_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.change_concretemixdesign' |
| `concrete_production` | `customer_request_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_customerrequest' |
| `concrete_production` | `customer_request_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_customerrequest' |
| `concrete_production` | `customer_request_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_customerrequest' |
| `concrete_production` | `customer_request_confirm` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.change_customerrequest' |
| `concrete_production` | `production_cost_per_m3` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_productionorder' |
| `concrete_production` | `production_order_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_schedule` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.change_productionorder' |
| `concrete_production` | `batch_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_productionbatch' |
| `concrete_production` | `production_daily` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_productionorder' |
| `concrete_production` | `batch_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_productionbatch' |
| `concrete_production` | `batch_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_productionbatch' |
| `concrete_production` | `batch_update_status` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.change_productionbatch' |
| `concrete_production` | `truck_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_truck' |
| `concrete_production` | `truck_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_truck' |
| `concrete_production` | `truck_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.change_truck' |
| `concrete_production` | `delivery_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_deliveryschedule' |
| `concrete_production` | `delivery_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_deliveryschedule' |
| `concrete_production` | `cost_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_productioncost' |
| `concrete_production` | `cost_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_productioncost' |
| `concrete_production` | `api_mix_components` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `api_available_trucks` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_truck' |
| `concrete_production` | `api_production_stats` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_productionorder' |
| `concrete_production` | `silo_dashboard` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_silo' |
| `concrete_production` | `cement_daily_inventory` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_silotransaction' |
| `concrete_production` | `silo_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_silo' |
| `concrete_production` | `silo_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_silo' |
| `concrete_production` | `silo_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_silo' |
| `concrete_production` | `silo_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.change_silo' |
| `concrete_production` | `silo_transaction_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.add_silotransaction' |
| `concrete_production` | `api_silo_stock` | ØµÙ„Ø§Ø­ÙŠØ©: 'concrete_production.view_silo' |
| `contractors` | `dashboard` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contractor' |
| `contractors` | `contractor_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contractor' |
| `contractors` | `contractor_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.add_contractor' |
| `contractors` | `contractor_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contractor' |
| `contractors` | `contractor_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.change_contractor' |
| `contractors` | `contract_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contract' |
| `contractors` | `contract_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.add_contract' |
| `contractors` | `contract_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contract' |
| `contractors` | `contract_edit` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.change_contract' |
| `contractors` | `contract_approve` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.change_contract' |
| `contractors` | `contract_close` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.change_contract' |
| `contractors` | `certificate_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_interimcertificate' |
| `contractors` | `certificate_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.add_interimcertificate' |
| `contractors` | `certificate_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_interimcertificate' |
| `contractors` | `certificate_approve` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.change_interimcertificate' |
| `contractors` | `certificate_post` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.change_interimcertificate' |
| `contractors` | `payment_list` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contractorpayment' |
| `contractors` | `payment_create` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.add_contractorpayment' |
| `contractors` | `payment_detail` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contractorpayment' |
| `contractors` | `payment_post` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.change_contractorpayment' |
| `contractors` | `api_contract_items` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contract' |
| `contractors` | `api_contractor_stats` | ØµÙ„Ø§Ø­ÙŠØ©: 'contractors.view_contractor' |
---

## ٧. قسم الإنتاج الموسّع (Deployment: Nginx + Gunicorn + systemd/nssm)

### 7.1 نظرة عامة
للإنتاج نوصي بالبنية: **Nginx** (وكيل عكسي + إنهاء TLS) ← **Gunicorn** (عدة عمال WSGI)
← **Django**. تُجمَع الملفات الثابتة بـ `collectstatic`، وتُدار العمليات كخدمات
(systemd على لينكس، أو NSSM على ويندوز).

### 7.2 إعداد Gunicorn (التطبيق الخلفي)
الأمر الأساسي:
```bash
gunicorn accounting_system.wsgi:application --bind 127.0.0.1:8012 --workers 3 --timeout 120
```
متغيّرات البيئة المطلوبة (`DJANGO_DEBUG=false`، `DJANGO_SECRET_KEY`، `DJANGO_ALLOWED_HOSTS`
، وعناوين الربط من `network.conf`). سكربت جاهز: `deploy/start_backend.bat`.

### 7.3 إعداد Nginx (الوكيل العكسي)
ملف `deploy/nginx_dual.conf` يستمع على العناوين المطلوبة ويعيد التوجيه إلى Gunicorn:
```nginx
upstream accounting_backend { server 127.0.0.1:8012; }
server {
    listen 192.168.1.31:8012;
    listen 196.218.24.45:8012;   # إن كان العنوان مُسنداً لواجهة الجهاز؛ وإلا استخدم 0.0.0.0 ووجِّه من الراوتر
    server_name _;
    client_max_body_size 20M;
    location /static/ { alias J:/2027/accounting_system/staticfiles/; expires 30d; access_log off; }
    location /media/  { alias J:/2027/accounting_system/media/; expires 7d; }
    location / {
        proxy_pass http://accounting_backend;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
إعادة تحميل بلا توقف: `nginx -s reload`.

### 7.4 خدمة systemd (لينكس)
`/etc/systemd/system/accounting.service`:
```ini
[Unit]
Description=Accounting Gunicorn
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/accounting_system
EnvironmentFile=/opt/accounting_system/.env
ExecStart=/opt/venv/bin/gunicorn accounting_system.wsgi:application --bind 127.0.0.1:8012 --workers 3
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
تفعيل: `systemctl daemon-reload && systemctl enable --now accounting`؛ وخدمة Nginx:
`systemctl enable --now nginx`.

### 7.5 تشغيل كخدمة ويندوز عبر NSSM
يحوّل NSSM أي سكربت إلى خدمة ويندوز:
```bat
nssm install Accounting "D:\python 3.15\python.exe" "J:7ccounting_system\deploy\start_backend.bat"
nssm set Accounting AppDirectory "J:7ccounting_system"
nssm start Accounting
```
ولإبقاء Nginx كخدمة استخدم `nginx-service` أو NSSM بالطريقة نفسها.

### 7.6 الملفات الثابتة وSSL
- جمع الثابت: `python manage.py collectstatic --noinput`.
- SSL: استخدم Certbot (Let's Encrypt) مع Nginx؛ فعّل `DJANGO_SECURE_SSL_REDIRECT=true`
  وأعد تشغيل العامل.

### 7.7 أوامر الإدارة والتبديل
- إعادة تحميل Nginx: `nginx -s reload`
- إعادة تشغيل العامل: `systemctl restart accounting` / `nssm restart Accounting`
- تغيير العناوين/المنفذ: عدّل `network.conf` ثم أعِد تحميل/تشغيل الخدمات (لا حاجة لتعديل الكود).
