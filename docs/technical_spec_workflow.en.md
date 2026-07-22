# Technical Specification Document — Workflow
## Integrated Accounting System — Tawaredat Trading Company

> An architectural/operational specification describing the project structure,
> workflow, screen-navigation mechanisms, libraries used, and the data flow
> between frontend and backend, with security and performance considerations.

---

## 1. Overview of Structure and Development Environment

### 1.1 System Architecture
The system is a **Server-Rendered** web application built on the Django framework
(MTV pattern: Model–Template–View). There is no separate SPA frontend; every
screen is rendered on the server and delivered as HTML. Consequently, the SPA
concepts of "Props / State" map to the following in the Django context:

| SPA concept | Equivalent in this system |
|---|---|
| Props | Template Context variables passed via `render()` |
| State (client) | Minimal JS state (menu collapse, partial fetch) |
| State (server) | Database (Models), Session, Cache |
| Navigation Source of Truth | The URL (path + query string) |

### 1.2 Project Structure (package layout)
```
accounting_system/          # project settings
├── settings.py             # settings (DB, ALLOWED_HOSTS, CELERY, network binding)
├── urls.py                 # root router (includes sub-apps)
├── celery.py               # Celery setup
└── middleware.py           # LoginThrottleMiddleware (login attempt throttling)
accounts/ sales/ purchases/ treasury/ assets/ hr/ reports/ documents/
warehouses/ company/ ai_analysis/ concrete_production/ contractors/ backups/
sync/ users/ audit/ budget/ currency/ bank-reconciliation/ notifications/
common/ recurring/ credit_notes/ cheques/ sales_returns/ purchase_returns/
stock_adjustments/ payment_receipts/   # Django apps (each: models, views, urls, templates)
common/                     # permissions, context processors, shared models
templates/base/             # base template (sidebar / topbar)
static/ staticfiles/ media/
requirements.txt  network.conf  run_multi.py  run.bat
```
Each "app" contains: `models.py`, `views.py`, `urls.py`, and a `templates/<app>/` folder.

### 1.3 Development & Runtime Environment
- **Language:** Python 3.15 (interpreter: `D:\python 3.15\python.exe`)
- **Framework:** Django 4.2.30 (LTS)
- **Database:** SQLite by default; switchable to PostgreSQL via
  `DJANGO_DB_ENGINE=postgres` + connection settings.
- **UI:** Bootstrap 5.3 + Cairo Font + Font Awesome 6.4 + Jazzmin (admin theme).
- **Runtime:** `run_multi.py` (multi-address binding) for development, or
  Nginx + Gunicorn in production (see `deploy/`).
- **Async tasks:** Celery 5.6.3 (eager mode by default, no broker needed).

---

## 2. Workflow

### 2.1 General Flow — from Login to Completing the Core Operation
1. **Authentication:** the user reaches `/accounts/login/`; Django authenticates,
   creates a session, and redirects (`?next=`) to the dashboard `/`.
2. **Dashboard:** shows indicators (via `dashboard_view` + reports); navigation
   via the permission-aware sidebar.
3. **Core operation — Concrete Sales Invoice cycle:**
   - a. `concrete_production:customer_request_create` ← customer request.
   - b. `concrete_production:production_order_create` ← production order linked to the request.
   - c. recording batches (`production_batch`) and deliveries (`delivery_schedule`).
   - d. on production order completion (`status='completed'`) a **Sales Invoice is
     auto-created** and linked (`SalesInvoice.production_order`) inside
     `transaction.atomic`, and its journal entry is posted.
   - e. `sales:sales_invoice_post` ← posts the journal entry (updates account
     balances atomically via `select_for_update`).
   - f. `sales:sales_invoice_print` / `whatsapp` ← print / send.
4. **Reports:** aggregated in `reports` (cached via `@cache_page`).

### 2.2 Inter-step Linking Mechanism
Each step ends with a `redirect()` to the next screen using `reverse()` with the
route name and the primary key (`pk`) in the path — keeping the **URL as the
Single Source of Truth** for navigation state:

```python
# concrete_production/views.py — after scheduling
return redirect('concrete_production:production_order_detail', pk=order.pk)
```

---

## 3. Screen Navigation Mechanisms

### 3.1 Internal Routing
- The root router `accounting_system/urls.py` includes apps via `include()` with
  an `app_name` (namespace) to avoid name collisions.
- Each app has a `urls.py` defining patterns and path converters:

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
`<uuid:pk>` extracts the primary key from the URL and passes it to the view.

### 3.2 Template Navigation
Templates use the `{% url %}` tag with the route name and namespace (never
hard-coded URLs):

```html
<a href="{% url 'sales:invoice_create' %}">Sales Invoice</a>
```
Highlighting the active screen by comparing `request.resolver_match.url_name`:
```html
<a href="{% url 'dashboard' %}"
   class="{% if request.resolver_match.url_name == 'dashboard' %}active{% endif %}">
   Dashboard
</a>
```
Passing data between screens via **query string** — example from the sidebar:
```html
<a href="{% url 'payment_receipts:create' %}?type=receipt">Receipt Voucher</a>
```
Read in the view via `request.GET.get('type')`.

### 3.3 "Props / State" in the Django Context
- **Props** = template context:
  ```python
  return render(request, 'concrete_production/production_order_detail.html', {
      'order': order, 'batches': batches, 'deliveries': deliveries, 'costs': costs,
  })
  ```
- **State — Database (entities linked across screens):** relationships (FK) link
  screens. Example linking an invoice to a production order:
  ```python
  # sales/models.py
  class SalesInvoice(models.Model):
      production_order = models.ForeignKey(
          'concrete_production.ProductionOrder', null=True, blank=True,
          on_delete=models.SET_NULL, related_name='sales_invoice')
  ```
  Shown in the order-detail template as: `{{ order.sales_invoice.invoice_number }}`.
- **State — Session:** branch / user data.
- **State — Context Processors:** injected into every template automatically:
  ```python
  # common/context_processors.py
  def user_permissions_context(request):
      if request.user.is_superuser:
          perms = {'all'}
      else:
          perms = set(request.user.get_all_permissions())
      return {'user_perms': perms, 'is_superuser': request.user.is_superuser}
  ```
  Used to show/hide sidebar links by permission:
  ```html
  {% if "all" in user_perms or "sales.add_salesinvoice" in user_perms %}
    <a href="{% url 'sales:invoice_create' %}">Sales Invoice</a>
  {% endif %}
  ```
- **State — Messages Framework:** one-time notifications between requests
  (`messages.success(request, '...')`).
- **State — Client (JS):** minimal. Example fetching partial data safely:
  ```javascript
  const data = JSON.parse(document.getElementById('chart-data').textContent);
  ```
  injected via `{{ chart_data_json|json_script:"chart-data" }}` (avoids XSS vs `|safe`).

---

## 4. Software and Libraries (versions and rationale)

| Library | Version | Role / reason |
|---|---|---|
| Python | 3.15 | Runtime interpreter |
| Django | 4.2.30 (LTS) | Web framework; long-term support, PostgreSQL ready |
| psycopg2-binary | >=2.9 | PostgreSQL driver when switching from SQLite |
| django-crispy-forms | 2.5 | Elegant form rendering with Bootstrap |
| crispy-bootstrap5 | 2026.3 | Bootstrap 5 support for crispy-forms |
| django-jazzmin | >=2.6 | Improved Django admin UI (RTL aware) |
| reportlab | >=4.0 | PDF reports / invoices |
| openpyxl | >=3.1 | Excel import / export |
| python-dateutil | >=2.8 | Date handling in reports |
| faker | >=20.0 | Dummy data for tests (`seed_dummy_data`) |
| Celery | 5.6.3 | Async tasks (balance recalculation) |
| redis (py) | 8.0.1 | Celery broker / result store (optional) |
| Bootstrap 5.3 / Font Awesome 6.4 / Cairo font | — | Arabic RTL interface |

---

## 5. Data Flow (Frontend ↔ Backend)

### 5.1 Textual and Visual Data-Flow Diagram
> A visual diagram (image + PDF) is available at: `docs/diagrams/data_flow.svg`
> and `docs/diagrams/data_flow.pdf` — illustrating the same flow below visually.

```
[Browser]
   │  GET /sales/invoices/<pk>/   (or POST form + csrfmiddlewaretoken)
   ▼
[Server: Nginx ← Gunicorn / runserver]
   │      (prod: Nginx listens on addresses, proxies to 127.0.0.1:8012)
   ▼
[Middleware]  →  LoginThrottleMiddleware, SessionMiddleware, CsrfViewMiddleware
   ▼
[URL Resolver]  →  matches path, calls View with params (pk)
   ▼
[View]  →  permission check (permission_required_or_login)
   │         →  ORM query (select_related / prefetch_related)
   │         ▼
   ▼      [Database: SQLite / PostgreSQL]
[Context]  ←  builds context dict (objects + context processors)
   ▼
[Template]  ←  renders HTML (DTL) + static assets
   ▼
[HTTP Response]  →  browser renders the screen
```
For partial data (JSON APIs) the View returns `JsonResponse` consumed by the
browser via `fetch`:
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

### 5.2 Security Considerations
- **CSRF:** `CsrfViewMiddleware` + `{% csrf_token %}` in every POST form; and
  `CSRF_TRUSTED_ORIGINS` derived from the bind addresses.
- **Permissions:** `@permission_required_or_login` + object-level check
  (`has_object_permission`) to block access to other branches.
- **ALLOWED_HOSTS:** derived from bind addresses (`SERVER_BIND_HOSTS`).
- **SECRET_KEY:** mandatory in production (raises if missing).
- **Login throttling:** `LoginThrottleMiddleware` (10 attempts / 5 min per IP → 429).
- **JSON injection:** `json_script` instead of `|safe`.
- **Secure cookies** (Secure/HSTS) when SSL is enabled via `DJANGO_SECURE_SSL_REDIRECT`.

### 5.3 Performance Considerations
- **Avoid N+1:** `select_related`/`prefetch_related` — example:
  `ProductionOrder.objects.select_related('customer_request__customer','mix_design')`.
- **Pagination:** `Paginator(queryset, 25)` with `?page=` switching.
- **Caching:** `@cache_page(300)` + `@vary_on_cookie` for heavy screens.
- **Heavy tasks:** balance recalculation via a Celery task (`recalc_balances_task`)
  instead of synchronous execution.
- **Concurrency safety:** critical stock updates inside `transaction.atomic()` +
  `select_for_update()` (e.g., `SiloTransaction.save`, `JournalEntry.post`) to
  avoid lost updates.

---

## 6. Screen Permission Matrix
> The table below was extracted automatically from the view decorators across
> all apps (covers 337 screens/functions). The symbol `— (public/no restriction)`
> means no permission decorator was found (some are protected by `login_required`
> only, and some API endpoints are protected by an API key instead of a Django
> permission). The full matrix is also saved in `docs/permissions_matrix.md`.

| App | View (function) | Required access / permission |
|---|---|---|
| `accounts` | `account_list` | Permission: 'accounts.view_account' |
| `accounts` | `account_create` | Login required |
| `accounts` | `account_detail` | Login required |
| `accounts` | `account_edit` | Login required |
| `accounts` | `account_statement` | Login required |
| `accounts` | `journal_list` | Permission: 'accounts.view_journalentry' |
| `accounts` | `journal_create` | Permission: 'accounts.add_journalentry' |
| `accounts` | `journal_detail` | Login required |
| `accounts` | `journal_post` | Login required |
| `accounts` | `trial_balance` | Login required |
| `accounts` | `chart_of_accounts` | Login required |
| `accounts` | `export_accounts` | Login required |
| `accounts` | `import_accounts` | Login required |
| `accounts` | `export_journal` | Login required |
| `accounts` | `fiscal_year_close` | Login required |
| `ai_analysis` | `dashboard` | Login required |
| `ai_analysis` | `analyze_error` | Login required |
| `ai_analysis` | `auto_detect` | Login required |
| `ai_analysis` | `error_history` | Login required |
| `ai_analysis` | `error_detail` | Login required |
| `ai_analysis` | `apply_solution` | HTTP method restricted: require_POST |
| `ai_analysis` | `api_detect_errors` | HTTP method restricted: require_POST |
| `ai_analysis` | `api_analyze_error` | HTTP method restricted: require_POST |
| `ai_analysis` | `api_error_stats` | Login required |
| `assets` | `asset_list` | Login required |
| `assets` | `asset_create` | Login required |
| `assets` | `asset_detail` | Login required |
| `assets` | `asset_edit` | Login required |
| `assets` | `depreciation_create` | Login required |
| `assets` | `asset_category_list` | Login required |
| `assets` | `asset_category_create` | Login required |
| `assets` | `export_assets` | Login required |
| `assets` | `import_assets` | Login required |
| `audit` | `audit_log_list` | Login required |
| `backups` | `_ensure_backup_dir` | — (عام/بلا قيد) |
| `backups` | `_format_size` | — (عام/بلا قيد) |
| `backups` | `_safe_extract_zip` | — (عام/بلا قيد) |
| `backups` | `backup_dashboard` | Login required |
| `backups` | `create_backup` | HTTP method restricted: require_POST |
| `backups` | `download_backup` | Login required |
| `backups` | `delete_backup` | HTTP method restricted: require_POST |
| `backups` | `restore_backup` | Login required |
| `backups` | `export_json` | Login required |
| `backups` | `import_json` | Login required |
| `backups` | `backup_settings_view` | Login required |
| `bank_reconciliation` | `reconciliation_dashboard` | Login required |
| `bank_reconciliation` | `session_create` | Login required |
| `bank_reconciliation` | `session_detail` | Login required |
| `bank_reconciliation` | `item_list` | Login required |
| `bank_reconciliation` | `item_create` | Login required |
| `bank_reconciliation` | `item_match` | Login required |
| `bank_reconciliation` | `import_csv` | Login required |
| `bank_reconciliation` | `auto_match` | Login required |
| `bank_reconciliation` | `item_delete` | HTTP method restricted: require_POST |
| `budget` | `cost_center_list` | Login required |
| `budget` | `cost_center_create` | Login required |
| `budget` | `budget_list` | Login required |
| `budget` | `budget_create` | Login required |
| `cheques` | `cheque_list` | Login required |
| `cheques` | `cheque_create` | Login required |
| `cheques` | `cheque_detail` | Login required |
| `cheques` | `cheque_update_status` | HTTP method restricted: require_POST |
| `cheques` | `cheque_delete` | HTTP method restricted: require_POST |
| `cheques` | `cheque_dashboard` | Login required |
| `common` | `whatsapp_webhook` | HTTP method restricted: require_http_methods |
| `company` | `company_settings` | Login required |
| `company` | `branch_create` | Login required |
| `company` | `branch_edit` | Login required |
| `company` | `branch_delete` | HTTP method restricted: require_POST |
| `company` | `admin_settings_dashboard` | Permission: 'accounts.change_accounttype', raise_exception=True |
| `company` | `account_type_create` | HTTP method restricted: require_http_methods |
| `company` | `account_type_update` | HTTP method restricted: require_http_methods |
| `company` | `account_type_delete` | HTTP method restricted: require_http_methods |
| `company` | `product_create` | HTTP method restricted: require_http_methods |
| `company` | `product_update` | HTTP method restricted: require_http_methods |
| `company` | `product_delete` | HTTP method restricted: require_http_methods |
| `company` | `category_create` | HTTP method restricted: require_http_methods |
| `company` | `category_update` | HTTP method restricted: require_http_methods |
| `company` | `category_delete` | HTTP method restricted: require_http_methods |
| `company` | `unit_create` | HTTP method restricted: require_http_methods |
| `company` | `unit_update` | HTTP method restricted: require_http_methods |
| `company` | `unit_delete` | HTTP method restricted: require_http_methods |
| `credit_notes` | `credit_note_list` | Login required |
| `credit_notes` | `credit_note_create` | Login required |
| `credit_notes` | `credit_note_detail` | Login required |
| `credit_notes` | `credit_note_post` | HTTP method restricted: require_POST |
| `credit_notes` | `credit_note_delete` | HTTP method restricted: require_POST |
| `currency` | `currency_list` | Login required |
| `currency` | `currency_create` | Login required |
| `currency` | `currency_edit` | Login required |
| `currency` | `exchange_rate_history` | Login required |
| `documents` | `document_type_list` | Login required |
| `documents` | `document_type_create` | Login required |
| `documents` | `document_type_edit` | Login required |
| `documents` | `document_template_list` | Login required |
| `documents` | `document_template_create` | Login required |
| `documents` | `document_template_edit` | Login required |
| `documents` | `document_list` | Login required |
| `documents` | `document_create` | Login required |
| `documents` | `document_detail` | Login required |
| `documents` | `document_edit` | Login required |
| `documents` | `document_action` | Login required |
| `documents` | `document_add_attachment` | Login required |
| `hr` | `employee_list` | Permission: 'hr.view_employee' |
| `hr` | `employee_create` | Permission: 'hr.add_employee' |
| `hr` | `employee_detail` | Permission: 'hr.view_employee' |
| `hr` | `employee_edit` | Permission: 'hr.change_employee' |
| `hr` | `attendance_list` | Permission: 'hr.view_attendance' |
| `hr` | `attendance_create` | Permission: 'hr.add_attendance' |
| `hr` | `salary_list` | Permission: 'hr.view_salary' |
| `hr` | `salary_create` | Permission: 'hr.add_salary' |
| `hr` | `salary_post` | HTTP method restricted: require_POST |
| `hr` | `department_list` | Permission: 'hr.view_department' |
| `hr` | `department_create` | Permission: 'hr.add_department' |
| `hr` | `export_employees` | Permission: 'hr.view_employee' |
| `hr` | `export_salaries` | Permission: 'hr.export_salary' |
| `hr` | `import_employees` | Permission: 'hr.add_employee' |
| `notifications` | `notification_dashboard` | Login required |
| `notifications` | `template_list` | Login required |
| `notifications` | `template_create` | Login required |
| `notifications` | `send_test_notification` | Login required |
| `payment_receipts` | `receipt_list` | Permission: 'treasury.view_bank' |
| `payment_receipts` | `receipt_create` | Login required |
| `payment_receipts` | `receipt_detail` | Login required |
| `payment_receipts` | `receipt_post` | HTTP method restricted: require_POST |
| `payment_receipts` | `receipt_delete` | HTTP method restricted: require_POST |
| `payment_receipts` | `receipt_print` | Login required |
| `payment_receipts` | `get_customer_invoices` | Login required |
| `payment_receipts` | `get_supplier_invoices` | Login required |
| `purchases` | `supplier_list` | Permission: 'purchases.view_supplier' |
| `purchases` | `supplier_create` | Permission: 'purchases.add_supplier' |
| `purchases` | `supplier_detail` | Permission: 'purchases.view_supplier' |
| `purchases` | `supplier_edit` | Permission: 'purchases.change_supplier' |
| `purchases` | `product_list` | Login required |
| `purchases` | `product_create` | Login required |
| `purchases` | `product_edit` | Login required |
| `purchases` | `catalog_settings` | Login required |
| `purchases` | `purchase_invoice_list` | Login required |
| `purchases` | `purchase_invoice_create` | Login required |
| `purchases` | `purchase_invoice_detail` | Login required |
| `purchases` | `purchase_invoice_post` | HTTP method restricted: require_POST |
| `purchases` | `purchase_invoice_print` | Login required |
| `purchases` | `purchase_invoice_whatsapp` | HTTP method restricted: require_POST |
| `purchases` | `supplier_statement_whatsapp` | HTTP method restricted: require_POST |
| `purchases` | `export_suppliers` | Login required |
| `purchases` | `import_suppliers` | Login required |
| `purchases` | `export_products` | Login required |
| `purchases` | `import_products` | Login required |
| `purchases` | `product_barcode_print` | Login required |
| `purchases` | `product_barcode_batch` | Login required |
| `purchases` | `product_price_list` | Login required |
| `purchase_returns` | `purchase_return_list` | Permission: 'purchases.view_purchaseinvoice' |
| `purchase_returns` | `purchase_return_create` | Login required |
| `purchase_returns` | `purchase_return_detail` | Login required |
| `purchase_returns` | `purchase_return_post` | HTTP method restricted: require_POST |
| `purchase_returns` | `purchase_return_delete` | HTTP method restricted: require_POST |
| `recurring` | `recurring_list` | Login required |
| `recurring` | `recurring_create` | Login required |
| `recurring` | `recurring_edit` | Login required |
| `recurring` | `recurring_execute` | Login required |
| `recurring` | `recurring_toggle` | Login required |
| `recurring` | `recurring_delete` | Login required |
| `recurring` | `_save_lines` | — (عام/بلا قيد) |
| `reports` | `_safe_parse_date` | — (عام/بلا قيد) |
| `reports` | `_validate_date_range` | — (عام/بلا قيد) |
| `reports` | `_get_date_range` | — (عام/بلا قيد) |
| `reports` | `dashboard_view` | Login required |
| `reports` | `financial_dashboard` | Permission: 'reports.view_reporttemplate' |
| `reports` | `_age_bucket` | — (عام/بلا قيد) |
| `reports` | `workflow_tracker` | Permission: 'reports.view_reporttemplate' |
| `reports` | `report_list` | Login required |
| `reports` | `income_statement` | Login required |
| `reports` | `balance_sheet` | Login required |
| `reports` | `trial_balance_report` | Login required |
| `reports` | `vat_return` | Login required |
| `reports` | `withholding_tax_report` | Login required |
| `reports` | `supplier_report` | Login required |
| `reports` | `supplier_detail_report` | Login required |
| `reports` | `customer_report` | Login required |
| `reports` | `customer_detail_report` | Login required |
| `reports` | `profit_margin_report` | Login required |
| `reports` | `asset_schedule` | Login required |
| `reports` | `payroll_report` | Login required |
| `reports` | `export_report` | Login required |
| `reports` | `_export_simple_xlsx` | — (عام/بلا قيد) |
| `reports` | `__init__` | — (عام/بلا قيد) |
| `reports` | `__getattr__` | — (عام/بلا قيد) |
| `reports` | `_export_daily_sales` | — (عام/بلا قيد) |
| `reports` | `_export_daily_purchases` | — (عام/بلا قيد) |
| `reports` | `_export_ar_aging` | — (عام/بلا قيد) |
| `reports` | `_export_ap_aging` | — (عام/بلا قيد) |
| `reports` | `_export_income_statement` | — (عام/بلا قيد) |
| `reports` | `_export_balance_sheet` | — (عام/بلا قيد) |
| `reports` | `_export_vat_return` | — (عام/بلا قيد) |
| `reports` | `_export_payroll` | — (عام/بلا قيد) |
| `reports` | `_export_inventory` | — (عام/بلا قيد) |
| `reports` | `_export_profit_margin` | — (عام/بلا قيد) |
| `reports` | `_export_withholding_tax` | — (عام/بلا قيد) |
| `reports` | `_export_supplier_report` | — (عام/بلا قيد) |
| `reports` | `_export_customer_report` | — (عام/بلا قيد) |
| `reports` | `_export_customer_statement` | — (عام/بلا قيد) |
| `reports` | `_export_supplier_statement` | — (عام/بلا قيد) |
| `reports` | `_export_trial_balance` | — (عام/بلا قيد) |
| `reports` | `_export_asset_schedule` | — (عام/بلا قيد) |
| `reports` | `_export_cash_flow` | — (عام/بلا قيد) |
| `reports` | `ar_aging_report` | Login required |
| `reports` | `ap_aging_report` | Login required |
| `reports` | `inventory_report` | Login required |
| `reports` | `customer_statement` | Login required |
| `reports` | `supplier_statement` | Login required |
| `reports` | `daily_sales_report` | Login required |
| `reports` | `daily_purchases_report` | Login required |
| `reports` | `cash_flow_report` | Login required |
| `sales` | `customer_list` | Permission: 'sales.view_customer' |
| `sales` | `customer_create` | Permission: 'sales.add_customer' |
| `sales` | `customer_detail` | Permission: 'sales.view_customer' |
| `sales` | `customer_edit` | Permission: 'sales.change_customer' |
| `sales` | `sales_invoice_list` | Permission: 'sales.view_salesinvoice' |
| `sales` | `sales_invoice_create` | Permission: 'sales.add_salesinvoice' |
| `sales` | `sales_invoice_detail` | Login required |
| `sales` | `sales_invoice_post` | HTTP method restricted: require_POST |
| `sales` | `sales_invoice_print` | Login required |
| `sales` | `sales_invoice_whatsapp` | HTTP method restricted: require_POST |
| `sales` | `customer_statement_whatsapp` | HTTP method restricted: require_POST |
| `sales` | `export_customers` | Login required |
| `sales` | `import_customers` | Login required |
| `sales_returns` | `sales_return_list` | Permission: 'sales.view_salesinvoice' |
| `sales_returns` | `sales_return_create` | Login required |
| `sales_returns` | `sales_return_detail` | Login required |
| `sales_returns` | `sales_return_post` | HTTP method restricted: require_POST |
| `sales_returns` | `sales_return_delete` | HTTP method restricted: require_POST |
| `stock_adjustments` | `adjustment_list` | Login required |
| `stock_adjustments` | `adjustment_create` | Login required |
| `stock_adjustments` | `adjustment_detail` | Login required |
| `stock_adjustments` | `adjustment_approve` | HTTP method restricted: require_POST |
| `stock_adjustments` | `adjustment_delete` | HTTP method restricted: require_POST |
| `sync` | `_get_or_create_machine` | — (عام/بلا قيد) |
| `sync` | `_verify_api_key` | — (عام/بلا قيد) |
| `sync` | `sync_dashboard` | Login required |
| `sync` | `sync_settings_view` | Login required |
| `sync` | `test_connection` | Login required |
| `sync` | `manual_sync` | Login required |
| `sync` | `sync_log_detail` | Login required |
| `sync` | `api_push` | HTTP method restricted: require_http_methods |
| `sync` | `api_pull` | HTTP method restricted: require_http_methods |
| `sync` | `api_status` | HTTP method restricted: require_http_methods |
| `sync` | `api_recalculate` | HTTP method restricted: require_http_methods |
| `treasury` | `bank_list` | Permission: 'treasury.view_bank' |
| `treasury` | `bank_create` | Permission: 'treasury.add_bank' |
| `treasury` | `bank_detail` | Permission: 'treasury.view_bank' |
| `treasury` | `bank_transaction_create` | Permission: 'treasury.add_banktransaction' |
| `treasury` | `safe_list` | Permission: 'treasury.view_safe' |
| `treasury` | `safe_create` | Permission: 'treasury.add_safe' |
| `treasury` | `safe_detail` | Permission: 'treasury.view_safe' |
| `treasury` | `safe_transaction_create` | Permission: 'treasury.add_safetransaction' |
| `treasury` | `export_banks` | Permission: 'treasury.view_bank' |
| `treasury` | `export_safes` | Permission: 'treasury.view_safe' |
| `treasury` | `import_banks` | Permission: 'treasury.add_bank' |
| `treasury` | `import_safes` | Permission: 'treasury.add_safe' |
| `users` | `clean_password2` | — (عام/بلا قيد) |
| `users` | `save` | — (عام/بلا قيد) |
| `users` | `user_list` | Login required |
| `users` | `user_create` | Login required |
| `users` | `user_edit` | Login required |
| `users` | `user_delete` | HTTP method restricted: require_POST |
| `users` | `group_list` | Login required |
| `users` | `group_create` | Login required |
| `users` | `group_edit` | Login required |
| `users` | `group_delete` | HTTP method restricted: require_POST |
| `users` | `change_password` | Login required |
| `warehouses` | `warehouse_list` | Permission: 'warehouses.view_warehouse' |
| `warehouses` | `warehouse_create` | Permission: 'warehouses.add_warehouse' |
| `warehouses` | `warehouse_edit` | Permission: 'warehouses.change_warehouse' |
| `warehouses` | `warehouse_detail` | Permission: 'warehouses.view_warehouse' |
| `warehouses` | `warehouse_product_add` | Permission: 'warehouses.add_warehouseproduct' |
| `warehouses` | `movement_list` | Permission: 'warehouses.view_stockmovement' |
| `warehouses` | `movement_create` | Permission: 'warehouses.add_stockmovement' |
| `warehouses` | `movement_detail` | Permission: 'warehouses.view_stockmovement' |
| `concrete_production` | `dashboard` | Permission: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_list` | Permission: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_create` | Permission: 'concrete_production.add_concretemixdesign' |
| `concrete_production` | `mix_design_detail` | Permission: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_edit` | Permission: 'concrete_production.change_concretemixdesign' |
| `concrete_production` | `customer_request_list` | Permission: 'concrete_production.view_customerrequest' |
| `concrete_production` | `customer_request_create` | Permission: 'concrete_production.add_customerrequest' |
| `concrete_production` | `customer_request_detail` | Permission: 'concrete_production.view_customerrequest' |
| `concrete_production` | `customer_request_confirm` | Permission: 'concrete_production.change_customerrequest' |
| `concrete_production` | `production_cost_per_m3` | Permission: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_list` | Permission: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_create` | Permission: 'concrete_production.add_productionorder' |
| `concrete_production` | `production_order_detail` | Permission: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_schedule` | Permission: 'concrete_production.change_productionorder' |
| `concrete_production` | `batch_list` | Permission: 'concrete_production.view_productionbatch' |
| `concrete_production` | `production_daily` | Permission: 'concrete_production.view_productionorder' |
| `concrete_production` | `batch_create` | Permission: 'concrete_production.add_productionbatch' |
| `concrete_production` | `batch_detail` | Permission: 'concrete_production.view_productionbatch' |
| `concrete_production` | `batch_update_status` | Permission: 'concrete_production.change_productionbatch' |
| `concrete_production` | `truck_list` | Permission: 'concrete_production.view_truck' |
| `concrete_production` | `truck_create` | Permission: 'concrete_production.add_truck' |
| `concrete_production` | `truck_edit` | Permission: 'concrete_production.change_truck' |
| `concrete_production` | `delivery_list` | Permission: 'concrete_production.view_deliveryschedule' |
| `concrete_production` | `delivery_create` | Permission: 'concrete_production.add_deliveryschedule' |
| `concrete_production` | `cost_list` | Permission: 'concrete_production.view_productioncost' |
| `concrete_production` | `cost_create` | Permission: 'concrete_production.add_productioncost' |
| `concrete_production` | `api_mix_components` | Permission: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `api_available_trucks` | Permission: 'concrete_production.view_truck' |
| `concrete_production` | `api_production_stats` | Permission: 'concrete_production.view_productionorder' |
| `concrete_production` | `silo_dashboard` | Permission: 'concrete_production.view_silo' |
| `concrete_production` | `cement_daily_inventory` | Permission: 'concrete_production.view_silotransaction' |
| `concrete_production` | `silo_list` | Permission: 'concrete_production.view_silo' |
| `concrete_production` | `silo_detail` | Permission: 'concrete_production.view_silo' |
| `concrete_production` | `silo_create` | Permission: 'concrete_production.add_silo' |
| `concrete_production` | `silo_edit` | Permission: 'concrete_production.change_silo' |
| `concrete_production` | `silo_transaction_create` | Permission: 'concrete_production.add_silotransaction' |
| `concrete_production` | `api_silo_stock` | Permission: 'concrete_production.view_silo' |
| `contractors` | `dashboard` | Permission: 'contractors.view_contractor' |
| `contractors` | `contractor_list` | Permission: 'contractors.view_contractor' |
| `contractors` | `contractor_create` | Permission: 'contractors.add_contractor' |
| `contractors` | `contractor_detail` | Permission: 'contractors.view_contractor' |
| `contractors` | `contractor_edit` | Permission: 'contractors.change_contractor' |
| `contractors` | `contract_list` | Permission: 'contractors.view_contract' |
| `contractors` | `contract_create` | Permission: 'contractors.add_contract' |
| `contractors` | `contract_detail` | Permission: 'contractors.view_contract' |
| `contractors` | `contract_edit` | Permission: 'contractors.change_contract' |
| `contractors` | `contract_approve` | Permission: 'contractors.change_contract' |
| `contractors` | `contract_close` | Permission: 'contractors.change_contract' |
| `contractors` | `certificate_list` | Permission: 'contractors.view_interimcertificate' |
| `contractors` | `certificate_create` | Permission: 'contractors.add_interimcertificate' |
| `contractors` | `certificate_detail` | Permission: 'contractors.view_interimcertificate' |
| `contractors` | `certificate_approve` | Permission: 'contractors.change_interimcertificate' |
| `contractors` | `certificate_post` | Permission: 'contractors.change_interimcertificate' |
| `contractors` | `payment_list` | Permission: 'contractors.view_contractorpayment' |
| `contractors` | `payment_create` | Permission: 'contractors.add_contractorpayment' |
| `contractors` | `payment_detail` | Permission: 'contractors.view_contractorpayment' |
| `contractors` | `payment_post` | Permission: 'contractors.change_contractorpayment' |
| `contractors` | `api_contract_items` | Permission: 'contractors.view_contract' |
| `contractors` | `api_contractor_stats` | Permission: 'contractors.view_contractor' |

---

## 7. Expanded Production Section (Deployment: Nginx + Gunicorn + systemd/nssm)

### 7.1 Overview
For production we recommend: **Nginx** (reverse proxy + TLS termination) <-
**Gunicorn** (multiple WSGI workers) <- **Django**. Static files are collected
with `collectstatic`, and processes are managed as services (systemd on Linux,
or NSSM on Windows).

### 7.2 Gunicorn Setup (backend application)
Basic command:
```bash
gunicorn accounting_system.wsgi:application --bind 127.0.0.1:8012 --workers 3 --timeout 120
```
Required environment variables (`DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS`, and bind addresses from `network.conf`). Ready-made
script: `deploy/start_backend.bat`.

### 7.3 Nginx Setup (reverse proxy)
`deploy/nginx_dual.conf` listens on the required addresses and proxies to Gunicorn:
```nginx
upstream accounting_backend { server 127.0.0.1:8012; }
server {
    listen 192.168.1.31:8012;
    listen 196.218.24.45:8012;   # if this address is assigned to a host interface; otherwise use 0.0.0.0 and forward from the router
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
Reload without downtime: `nginx -s reload`.

### 7.4 systemd Service (Linux)
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
Enable: `systemctl daemon-reload && systemctl enable --now accounting`; and Nginx:
`systemctl enable --now nginx`.

### 7.5 Windows Service via NSSM
NSSM turns any script into a Windows service:
```bat
nssm install Accounting "D:\python 3.15\python.exe" "J:\2027\accounting_system\deploy\start_backend.bat"
nssm set Accounting AppDirectory "J:\2027\accounting_system"
nssm start Accounting
```
To keep Nginx as a service use `nginx-service` or NSSM the same way.

### 7.6 Static Files and SSL
- Collect static: `python manage.py collectstatic --noinput`.
- SSL: use Certbot (Let's Encrypt) with Nginx; enable `DJANGO_SECURE_SSL_REDIRECT=true`
  and restart the worker.

### 7.7 Management and Switch Commands
- Reload Nginx: `nginx -s reload`
- Restart worker: `systemctl restart accounting` / `nssm restart Accounting`
- Change addresses/port: edit `network.conf` then reload/restart the services
  (no code change needed).
