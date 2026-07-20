# خطة نقل برنامج احترافية بين الأجهزة (Migration & Deployment Plan)
> خاصة بنظام المحاسبة المتكامل — Django + SQLite/PostgreSQL — شركة تواريدات للتجارة.

## مبدأ عام
نقل برنامج Django لا يعني «نسخ المجلد فقط». العوامل الحقيقية المسببة للأعطال هي:
**اختلاف إصدار مفسّر Python، اختلاف مكتبات النظام (Visual C++/خطوط)، فقدان
قاعدة البيانات والوسائط، وتعارض متغيرات البيئة**. لذلك نعتمد نهجًا قائمًا على:
**حصر صريح ← عزل البيئة ← نقل البيانات المصدرية ← تحقق تلقائي ← اختبار ← تراجع آمن**.

---

## المرحلة الأولى — حصر المكونات المطلوب نقلها

### ١-١ شجرة الملفات المصدرية (الواجب نقلها)
```
accounting_system/
├── requirements.txt          # قائمة الاعتماديات (المصدر الوحيد للحقيقة)
├── network.conf             # عناوين الربط (LAN/خارجي/منفذ)
├── .env  (أو .env.example)  # المتغيرات البيئية السرية
├── run_multi.py / run.bat   # تشغيل التطبيق (بيئة التطوير)
├── accounting_system/       # الإعدادات والـ celery
├── <apps>/ + templates/ + static/   # كود التطبيق
├── media/                   # ملفات المستخدمين المرفوعة (بيانات حقيقية!)
├── db.sqlite3               # قاعدة البيانات المحلية (إن لم تُستخدم PostgreSQL)
└── staticfiles/             # يمكن إعادة توليدها عبر collectstatic
```
> **لا تُنقل** `staticfiles/` إلزاميًا (يُعاد توليدها)، **بل يجب** نقل `media/` و`db.sqlite3`
> لأنها تحوي بيانات العمل الفعلية.

### ١-٢ الاعتماديات البرمجية
- `requirements.txt` يحوي: `Django>=4.2, psycopg2-binary, django-crispy-forms,
  crispy-bootstrap5, reportlab, openpyxl, django-jazzmin, python-dateutil, faker,
  celery, redis`.
- مكتبات نظام ضرورية على Windows: **Visual C++ Redistributable** (مطلوب لـ `psycopg2`
  إن استُخدم PostgreSQL)، وخط **Cairo** (للواجهة العربية) — يُثبَّت يدويًا على الجهاز الهدف.

### ١-٣ إعدادات البيئة والمتغيرات
أنشئ ملف `.env` على الجهاز الهدف يحوي (مثال):
```ini
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<مفتاح عشوائي طويل>
DJANGO_DB_ENGINE=sqlite          # أو postgres
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.31,196.218.24.45
# إن استخدمت Celery غير متزامن:
DJANGO_CELERY_EAGER=false
DJANGO_CELERY_BROKER=redis://127.0.0.1:6379/0
```
متغيرات البيئة المدعومة في `settings.py`:
`DJANGO_BIND_HOSTS`, `DJANGO_BIND_PORT`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_DB_ENGINE`,
`DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`,
`DJANGO_DB_PORT`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_CELERY_EAGER`,
`DJANGO_CELERY_BROKER`.

### أدوات المرحلة
`tree` / `robocopy` (Windows) أو `rsync` (Linux) لنقل الملفات؛ `7z` لضغط الأرشيف.

---

## المرحلة الثانية — التحقق من توافق البيئة الجديدة

### ٢-١ توافق مفسّر Python
برنامجنا مبني على **Python 3.15** (مفسّرنا في المسار `D:\python 3.15\python.exe`،
و`pip` الافتراضي في الجهاز قد يكون Anaconda 3.13 — خطأ شائع). على الجهاز الهدف:
```powershell
& "D:\python 3.15\python.exe" --version      # يجب أن يطبع Python 3.15.x
& "D:\python 3.15\python.exe" -m pip --version
```
تأكد من تطابق **bitness** (32/64) بين الجهازين.

### ٢-٢ مطابقة الاعتماديات (الحقيقة مقابل المطلوب)
أنشئ على الجهاز القديم «بصمة» الحزم، وقارنها على الجهاز الجديد:
```powershell
# على الجهاز القديم
& "D:\python 3.15\python.exe" -m pip freeze > old_env.txt
# على الجهاز الجديد بعد التثبيت
& "D:\python 3.15\python.exe" -m pip freeze > new_env.txt
# مقارنة
Compare-Object (Get-Content old_env.txt) (Get-Content new_env.txt)
```
الحل القياسي: على الجهاز الجديد شغّل فقط `pip install -r requirements.txt`
داخل بيئة معزولة — فيضمن تطابق الإصدارات آليًا.

### ٢-٣ فحص المتغيرات وملفات التكوين
- تأكد من وجود `network.conf` وأن العناوين تخص الجهاز الجديد (IP الداخلي غالبًا يتغير).
- تأكد من أن `MEDIA_ROOT`/`STATIC_ROOT` قابلان للكتابة على الجهاز الجديد.

### أدوات المرحلة
`pip freeze`, `Compare-Object`, `python -c "import django; print(django.VERSION)"`.

---

## المرحلة الثالثة — عزل البرنامج عن بيئة النظام

### ٣-١ البيئة الافتراضية (Virtualenv) — الحل الأبسط
```powershell
& "D:\python 3.15\python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
```
هكذا يصبح كل شيء معزولًا عن Anaconda/النظام ولا يتعارض.

### ٣-٢ الحاويات (Docker) — الحل الأمتن للإنتاج
أدوات جاهزة مرفقة في المستودع: `Dockerfile`, `docker-compose.yml`,
`docker-entrypoint.sh`, `.dockerignore`. التشغيل:
```bash
cp .env.example .env      # عدّل القيم
docker compose up -d --build
```
الحاوية تحمل كل الاعتماديات ومكتبات النظام، فلا تأثير لاختلاف الجهاز المضيف.
يرجى مراجعة متغيّرات البيئة في `docker-compose.yml` (محرك قاعدة البيانات، العناوين).

### أدوات المرحلة
`venv`, `virtualenv`, `Docker`, `docker-compose`, `gunicorn`.

---

## المرحلة الرابعة — قائمة مرجعية للاختبار بعد النقل

| # | الفحص | الأمر/الخطوة |
|---|---|---|
| 1 | سلامة الإعدادات | `python manage.py check --deploy` |
| 2 | تطابق قاعدة البيانات | `python manage.py migrate --check` |
| 3 | توليد الثابت | `python manage.py collectstatic --noinput` |
| 4 | تسجيل الدخول | فتح `/accounts/login/` بصلاحيات `admin` |
| 5 | الربط الشبكي | `curl http://192.168.1.31:8012/` يرجع 200 |
| 6 | المزامنة (API) | `python manage.py test sync` |
| 7 | إعادة حساب الأرصدة | تشغيل `recalc_balances_task` |
| 8 | تقرير PDF | تصدير فاتورة وتوليد PDF |
| 9 | الوسائط | رفع/تنزيل ملف من `media/` |
| 10 | الصلاحيات | التحقق من إخفاء روابط بلا صلاحية |

تشغيل كامل الاختبارات: `python manage.py test`.

---

## المرحلة الخامسة — الإجراءات الاحتياطية (Rollback)

### ٥-١ نسخة احتياطية كاملة قبل أي شيء
```powershell
# أرشيف كامل للمشروع + قاعدة البيانات + الوسائط
7z a backup_pre_migration.7z db.sqlite3 media/ network.conf .env
```
احفظها خارج الجهاز الهدف (قرص خارجي/سحابة).

### ٥-٢ التراجع عند الفشل
- إن فشلت الهجرة: أعد `db.sqlite3` من النسخة، وشغّل `migrate` من الصفر.
- إن ظهر `SECRET_KEY` غير متطابق (جلسات/توقيعات مكسورة): ثبّت نفس القيمة القديمة
  مؤقتًا ثم غيّرها لاحقًا مع إعلام المستخدمين بإعادة الدخول.
- ⚠️ **تنبيه أمني مهم**: نسخة `dist/` الحالية في المشروع تحوي `SECRET_KEY` ثابتًا
  (`django-insecure-...`). لا تُوزّعها للإنتاج — استبدلها بـ `.env` عبر
  `DJANGO_SECRET_KEY` كما في `settings.py` الأصلية.

### ٥-٣ مراقبة الأخطاء أثناء أول تشغيل
- فعّل `DJANGO_DEBUG=true` مؤقتًا لرؤية التتبعات، ثم أطفئه.
- راجع سجلات Gunicorn/Nginx (`nginx -s reload` + سجلات `error.log`).

### أدوات المرحلة
`7z`, `pg_dump` (إن استُخدم PostgreSQL), `robocopy /MIR` لاسترجاع مجلد, سجلات النظام.

---

## ملخص تدفق التنفيذ
```
حصر (requirements/network.conf/.env/media/db)
  → عزل (venv أو Docker)
  → نقل + pip install -r requirements.txt
  → check + migrate + collectstatic
  → اختبار الشبكة والوظائف (الجدول ٤)
  → تفعيل الإنتاج (Gunicorn+Nginx)
  ← تراجع عبر backup_pre_migration.7z عند أي فشل
```
