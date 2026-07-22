# TECHNICAL MIGRATION GUIDE — دليل النقل والترقية التقني

> اسم الملف المرجعي: `docs/TECHNICAL_MIGRATION_GUIDE.md`
> نظام المحاسبة المتكامل لإنتاج الخرسانة — ERP v1.0

---

## 1. نظرة عامة

هذا الدليل يغطي ثلاثة سيناريوهات:
- **أ)** نقل النسخة من جهاز إلى جهاز آخر (كود + بيانات + إعدادات).
- **ب)** ترقية قاعدة البيانات من SQLite إلى PostgreSQL (للإنتاج/التزامن متعدد الأجهزة).
- **ج)** التحديث عبر Git + CI/CD (ترقية الإصدار).

## 2. سيناريو (أ): النقل لجهاز جديد

### 2.1 على الجهاز القديم — نسخة احتياطية كاملة
```powershell
cd D:\accounting_system
powershell -ExecutionPolicy Bypass -File create_full_backup.ps1
# ينتج: D:\accounting_system_backups\accounting_system_FULL_<timestamp>.zip
```
تشمل النسخة: الكود، `db.sqlite3`، `media/`، `.env` (تأكد من استثناء السرّيات عند النقل).

### 2.2 على الجهاز الجديد — فك الضغط وتجهيز البيئة
```powershell
# فك الضغط إلى D:\accounting_system
cd D:\accounting_system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
```
ثم شغّل: `python manage.py runserver 127.0.0.1:8001`

## 3. سيناريو (ب): SQLite ← PostgreSQL

استخدم السكربتات الجاهزة (راجع `MIGRATION_GUIDE.md` للتفاصيل):
```powershell
# 1) على جهاز قاعدة البيانات
powershell -ExecutionPolicy Bypass -File setup_postgresql_server.ps1
# 2) على كل جهاز تطبيق
powershell -ExecutionPolicy Bypass -File update_env_postgresql.ps1
# 3) على الجهاز القديم (مرة واحدة) لنقل البيانات
powershell -ExecutionPolicy Bypass -File migrate_sqlite_to_postgresql.ps1
```

متغيرات البيئة لـ PostgreSQL:
```
DJANGO_DB_ENGINE=postgres
DJANGO_DB_HOST=192.168.1.100
DJANGO_DB_PORT=5432
DJANGO_DB_NAME=accounting_db
DJANGO_DB_USER=accounting_user
DJANGO_DB_PASSWORD=كلمة_قوية
```

## 4. سيناريو (ج): الترقية عبر Git

```bash
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
# في الإنتاج (Docker):
docker compose up -d --build
docker compose exec -T web python manage.py migrate --noinput
```

## 5. نقل عبر Docker (موصى به للإنتاج)

```bash
# على الخادم
git clone https://github.com/itconstec55-bot/ERP.git ~/erp
cd ~/erp
# أنشئ .env فيه DJANGO_SECRET_KEY و DJANGO_DB_PASSWORD
docker compose up -d --build
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py collectstatic --noinput
```

## 6. نقاط حرجة عند النقل

| الخطوة | تحقق |
|--------|------|
| الإعدادات | `DJANGO_SECRET_KEY` قوي وثابت (لا تغيره بعد الإنتاج وإلا بطلت الجلسات). |
| قاعدة البيانات | شغّل `migrate` دائماً بعد سحب تحديث (توجد migrations مولّدة آلياً). |
| الوسائط | انسخ `media/` وإلا ستفقد المرفقات والصور. |
| الصلاحيات | أنشئ مستخدم admin جديد على الجهاز الجديد إن لزم. |
| الكاش | بعد النقل امسح كاش الصلاحيات (`cache.clear()`). |
| المنفذ | تجنّب تعارض المنفذ (8001 تطوير، 8012 إنتاج). |

## 7. استعادة من نسخة احتياطية

```bash
# استعادة DB نصية
python manage.py loaddata backup.json
# أو استبدال ملف db.sqlite3 مباشرة (مع إيقاف الخدمة أولاً)
```

## 8. التحقق بعد النقل

```bash
python manage.py check
curl -I http://127.0.0.1:8012/monitoring/   # يجب أن يعيد HTTP 200
python -m pytest --ds=accounting_system.settings -q   # 183 اختبار
```
