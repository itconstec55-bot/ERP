# Accounting System - نقل النسخة للجهاز الجديد (PostgreSQL Central)

---

## 📋 الملفات الجاهزة

| الملف | الغرض |
|--------|-------|
| `create_full_backup.ps1` | **إنشاء نسخة مضغوطة كاملة** (كود + DB + تكوينات) |
| `setup_postgresql_server.ps1` | **إعداد PostgreSQL كقاعدة مركزية** (على جهاز واحد) |
| `update_env_postgresql.ps1` | **تحديث .env** على كل جهاز للاتصال بـ PostgreSQL |
| `migrate_sqlite_to_postgresql.ps1` | **نقل البيانات** من SQLite لـ PostgreSQL (مرة واحدة) |

---

## 🚀 العملية الكاملة (Step by Step)

### المرحلة 1: على الجهاز القديم - إنشاء النسخة الاحتياطية
```powershell
cd D:\accounting_system
powershell -ExecutionPolicy Bypass -File create_full_backup.ps1
```
**الناتج:** `D:\accounting_system_backups\accounting_system_FULL_20260715_174448.zip` (~1 GB)

---

### المرحلة 2: اختيار جهاز قاعدة البيانات (السيرفر)

**الخيار أ: الجهاز القديم هو السيرفر** (إذا قوي: 8GB+ RAM، SSD)
- شغل عليه: `setup_postgresql_server.ps1`

**الخيار ب: الجهاز الجديد هو السيرفر** (موصى به للأداء)
- انقل الـ zip للجهاز الجديد، فك الضغط، شغل `setup_postgresql_server.ps1`

**الخيار ج: سيرفر منفصل** (أفضل للإنتاج)
- جهاز مخصص لقاعدة البيانات

---

### المرحلة 3: على جهاز قاعدة البيانات - تثبيت PostgreSQL
```powershell
# على الجهاز المختار كـ DB Server
cd D:\accounting_system
powershell -ExecutionPolicy Bypass -File setup_postgresql_server.ps1
```

**ماذا يفعل:**
1. ✅ يثبت PostgreSQL 16 (via winget)
2. ✅ يخلق قاعدة: `accounting_db`
3. ✅ يخلق مستخدم: `accounting_user`
4. ✅ يضبط `postgresql.conf` للأداء
5. ✅ يفتح `pg_hba.conf` للاتصال من الشبكة
6. ✅ يفتح جدار الحماية على المنفذ 5432
7. ✅ **يطبع معلومات الاتصال** (احفظها!)

**معلومات الاتصال التي ستظهر:**
```
Server IP: 192.168.1.100
Port: 5432
Database: accounting_db
User: accounting_user
Password: [م généré عشوائي قوي]
DATABASE_URL=postgresql://user:pass@192.168.1.100:5432/accounting_db
```

---

### المرحلة 4: على كل جهاز تطبيق (القديم + الجديد) - تحديث الاتصال

**على الجهاز القديم:**
```powershell
cd D:\accounting_system
# عدل المتغيرات في أول الملف:
# $DB_SERVER_IP = "192.168.1.100"  # IP جهاز قاعدة البيانات
# $DB_PASSWORD = "نفس_الباسوورد_من_السيرفر"
powershell -ExecutionPolicy Bypass -File update_env_postgresql.ps1
```

**على الجهاز الجديد:**
```powershell
# 1. فك الضغط
# 2. cd للمجلد
# 3. عدل المتغيرات في update_env_postgresql.ps1
powershell -ExecutionPolicy Bypass -File update_env_postgresql.ps1
```

**ماذا يفعل:** يحدث `.env` ليعمل `DATABASE_URL` يشير لـ PostgreSQL

---

### المرحلة 5: على الجهاز القديم فقط - نقل البيانات
```powershell
cd D:\accounting_system
powershell -ExecutionPolicy Bypass -File migrate_sqlite_to_postgresql.ps1
```
**ماذا يفعل:**
1. ✅ يصدر كل البيانات من SQLite إلى JSON
2. ✅ يطبق `migrate` على PostgreSQL (يخلق الجداول)
3. ✅ يستورد البيانات في PostgreSQL
4. ✅ يحتفظ بنسخة احتياطية من SQLite

---

### المرحلة 6: على الجهاز الجديد - تجهيز البيئة
```powershell
cd D:\accounting_system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install psycopg2-binary
python manage.py migrate
python manage.py collectstatic
```

---

### المرحلة 7: تشغيل البذور (على جهاز واحد فقط)
```powershell
python run_seed.py
# أو
run_seed.bat
```

---

### المرحلة 8: التشغيل
```powershell
# على الجهازين:
python run_waitress.py
# أو
start_production.bat
```

---

## 📋 Checklist النهائي

- [ ] النسخة الاحتياطية 만들어진 (`create_full_backup.ps1`)
- [ ] PostgreSQL منصّب ومعد (`setup_postgresql_server.ps1`)
- [ ] معلومات الاتصال محفوظة (IP, User, Pass, DB_NAME)
- [ ] `.env` محدث على الجهاز القديم (`update_env_postgresql.ps1`)
- [ ] `.env` محدث على الجهاز الجديد (`update_env_postgresql.ps1`)
- [ ] البيانات منقولة (`migrate_sqlite_to_postgresql.ps1`)
- [ ] `migrate` و `collectstatic` على الجهاز الجديد
- [ ] `run_seed.py` على جهاز واحد
- [ ] التطبيق يعمل على الجهازين: `http://<IP>:8000`

---

## 🔧 استكشاف الأخطاء

| المشكلة | الحل |
|----------|-------|
| `psql: connection refused` | تأكد أن السيرفر يعمل: `services.msc` → PostgreSQL، وفتح جدار الحماية |
| `FATAL: password authentication failed` | تأكد من `$DB_PASSWORD` مطابق في `.env` والسيرفر |
| `django.db.utils.OperationalError: could not connect` | جرب `ping <DB_IP>` و `telnet <DB_IP> 5432` |
| `duplicate key value violates unique constraint` | امسح قاعدة PostgreSQL وأعد `migrate` ثم `loaddata` |
| بطء في الاستيراد | زد `maintenance_work_mem` في `postgresql.conf` وأعد تشغيل الخدمة |

---

## 📁 أين أجد الملفات؟
```
D:\accounting_system\
├── create_full_backup.ps1           ← شغل أولاً
├── setup_postgresql_server.ps1      ← على جهاز DB
├── update_env_postgresql.ps1        ← على كل جهاز تطبيق
├── migrate_sqlite_to_postgresql.ps1 ← على الجهاز القديم مرة واحدة
└── accounting_system_FULL_*.zip     ← النسخة المضغوطة (في D:\accounting_system_backups\)
```

---

## 💡 نصيحة: Docker بدلاً من التثبيت اليدوي؟
إذا تفضل Docker، استخدم `docker-compose.yml` الموجود:
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: accounting_db
      POSTGRES_USER: accounting_user
      POSTGRES_PASSWORD: your_strong_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  app:
    build: .
    environment:
      DATABASE_URL: postgresql://accounting_user:your_strong_password@db:5432/accounting_db
    depends_on:
      - db
    ports:
      - "8000:8000"
```
```bash
docker-compose up -d
docker-compose exec app python manage.py migrate
docker-compose exec app python run_seed.py
```
