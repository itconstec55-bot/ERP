# دليل التشغيل والإيقاف (Run & Stop Guide)

> اسم الملف المرجعي: `docs/run_stop_guide.md`
> ينطبق على: نظام المحاسبة المتكامل لإنتاج الخرسانة (ERP) — الإصدار 1.0

---

## 1. المتطلبات قبل التشغيل

- Python 3.12 (مثبّت وإضافته إلى PATH).
- ملف `.env` في جذر المشروع يحوي على الأقل:
  ```
  DJANGO_SECRET_KEY=مفتاح_سري_قوي_عشوائي
  DJANGO_DEBUG=false
  DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,الدومين_إن_وُجد
  ```
- قاعدة البيانات: افتراضياً SQLite (لا إعداد مطلوب). للإنتاج استخدم Postgres عبر
  `DJANGO_DB_ENGINE=postgres` ومتغيرات `DJANGO_DB_HOST/USER/PASSWORD/NAME`.

## 2. التشغيل في بيئة التطوير (Windows)

افتح موجه الأوامر داخل مجلد المشروع:

```bat
venv\Scripts\activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver 127.0.0.1:8001
```

ثم افتح المتصفح على: http://127.0.0.1:8001

## 3. التشغيل في الإنتاج (Docker Compose)

```bash
# على خادم لينكس بعد استنساخ المستودع وإنشاء .env
docker compose pull
docker compose up -d --build
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py collectstatic --noinput
```

الخدمة تعمل على المنفذ `8012` (قابل للتغيير عبر `BIND_PORT`).
للتحقق: `docker compose ps` وزيارة `http://الخادم:8012/monitoring/`.

## 4. النشر التلقائي عبر CI/CD (GitHub Actions)

عند كل `push` على `main`/`develop` يُشغّل خط أنابيب ينفّذ:
`test` (ruff + django check + pytest) ← `build` (collectstatic) ← `deploy` (SSH → Docker).

النشر يتطلب أسرار المستودع: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`
(واختيارياً `DEPLOY_PORT`, `DEPLOY_PATH`). إن لم تُضبط الأسرار، يتخطى النشر بأمان
ويبقى الـ pipeline أخضر. إن فشل الاتصال بالخادم أثناء النشر، **لا يكسر** الـ pipeline
(مُهيّأ بـ `continue-on-error`).

## 5. الإيقاف

### وضع التطوير (runserver)
أغلق نافذة الأوامر أو اضغط `Ctrl+C`.

### وضع الإنتاج (Docker)
```bash
docker compose down          # إيقاف الحاويات مع إبقاء البيانات (volumes)
docker compose down -v       # إيقاف وحذف مجلدات البيانات (تحذير: يمسح DB والوسائط)
```

### إيقاف خدمة تعمل في الخلفية (إذا شغّلت يدوياً عبر gunicorn)
```bash
pkill -f "gunicorn accounting_system.wsgi"
```

## 6. إعادة التشغيل بعد التعديل

```bash
git pull
docker compose up -d --build
docker compose exec -T web python manage.py migrate --noinput
```

## 7. لوحة المراقبة (Monitoring Dashboard)

متاحة على `/monitoring/` وتعرض: استخدام المعالج (CPU)، الذاكرة (RAM)، القرص (Disk)،
الشبكة، زمن التشغيل (Uptime)، وحالة خدمات قاعدة البيانات، وتتحدث تلقائياً كل 30 ثانية.
واجهة برمجية للقياس: `/monitoring/api/metrics/` و `/monitoring/api/history/`.

## 8. النسخ الاحتياطي

- آلي: يُنفَّذ حسب جدولة النظام (راجع شاشة النسخ الاحتياطي في التطبيق).
- يدوي: انسخ `db.sqlite3` و`media/` وملف `.env`.
- عبر الأمر: `python manage.py dumpdata > backup.json` للتصدير النصي.
