# دليل استكشاف الأخطاء (Troubleshooting Guide)

> اسم الملف المرجعي: `docs/troubleshooting.md`
> نظام المحاسبة المتكامل لإنتاج الخرسانة — ERP v1.0

---

## 1. الخادم لا يقلع

**العرض:** `ImportError` أو `ModuleNotFoundError`
**السبب الشائع:** المتطلبات غير مثبّتة أو venv غير مُفعّل.
**الحل:**
```bat
venv\Scripts\activate
pip install -r requirements.txt
```

**العرض:** `django.core.exceptions.ImproperlyConfigured: DJANGO_SECRET_KEY`
**الحل:** تأكد من وجود `.env` فيحتوي `DJANGO_SECRET_KEY=...` (اجعله قوياً:
`python -c "import secrets;print(secrets.token_urlsafe(50))"`).

## 2. خطأ في قاعدة البيانات

**العرض:** `NOT NULL constraint failed: <جدول>.<حقل>`
**السبب:** نموذج عُدّل بإضافة حقل مطلوب دون migration.
**الحل:**
```bat
python manage.py makemigrations <app>
python manage.py migrate
```

**العرض:** `Database is locked` (SQLite)
**الحل:** أغلق كل نسخ التطبيق، احذف `db.sqlite3-wal` و`db.sqlite3-shm`، أعد التشغيل.

**العرض:** فشل الاتصال بـ Postgres
**الحل:** تحقق من `DJANGO_DB_HOST/PORT/USER/PASSWORD/NAME` وأن الخدمة تعمل
وقاعدة `accounting` موجودة.

## 3. ملفات ثابتة (Static Files)

**العرض:** تنسيقات مكسورة (CSS/JS لا تُحمّل)
**الحل:**
```bat
python manage.py collectstatic --noinput
```
وفي الإنتاج تأكد أن خدمة Gunicorn/Nginx تشير إلى مجلد `staticfiles/`.

## 4. صفحات 500 / 404

**العرض:** خطأ 500
**الحل:** راجع `logs/accounting.log` و`logs/errors.log`. فعّل
`DJANGO_DEBUG=true` مؤقتاً للتشخيص (لا تُبقه في الإنتاج!).

**العرض:** 404 على مسار مراقبة
**الحل:** المسار الصحيح `/monitoring/` (بار ويُغلق بـ slash).

## 5. فشل خط أنابيب CI/CD

**العرض:** `Invalid workflow file ... Unrecognized named-value: 'secrets'`
**السبب:** استخدام `secrets` داخل `if:` (غير مسموح في GitHub Actions).
**الحل:** ضع الأسرار في `env:` أو داخل `run:`، ولا تستخدمها في `if:`.

**العرض:** فشل خطوة النشر (exit 255)
**السبب:** الخادم غير متاح أو المفتاح غير مطابق.
**ملاحظة:** النشر مُهيّأ `continue-on-error` فلا يكسر الـ pipeline؛ راجع
الأسرار `DEPLOY_HOST/USER/SSH_KEY` وحالة جدار الحماية على المنفذ 22.

**العرض:** فشل ruff محلياً
**الحل:** `ruff check --fix .` ثم `ruff format .` لمعالجة التنسيق تلقائياً.

## 6. مشاكل الصلاحيات (Access Control)

**العرض:** مستخدم محروم من شاشة يملكها
**السبب:** كاش صلاحيات `access_control.resolver` (TTL 300s).
**الحل:** امسح الكاش: `python -c "from django.core.cache import cache; cache.clear()"`
أو أعد تشغيل العامل. (أثناء الاختبارات نُصلحه بـ `cache.clear()` في setUp.)

## 7. الإنتاج الخرساني (Concrete)

**العرض:** `SiloTransaction` لا يحدّث مخزون السيلة
**الحل:** تأكد أن الإشارة (signal) مُسجَّلة (`concrete_production/apps.ready`)،
وراجع `TestSiloTransactions` للسلوك المتوقع.

**العرض:** تكلفة الإنتاج لكل م³ غير دقيقة
**الحل:** راجع `ProductionCost` و`ProductionBatch`؛ التكلفة تُجمَّع من
مكوّنات الخلطة + العمالة + التشغيل.

## 8. أدوات تشخيص سريعة

```bat
python manage.py check            # فحص سلامة الإعدادات
python deployment/health_check.py # فحص صحة الخدمات
python deployment/service.py status
python manage.py shell             # فحص تفاعلي للنماذج
```
