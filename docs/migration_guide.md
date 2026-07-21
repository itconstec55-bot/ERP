# دليل شامل لنقل وترحيل البرنامج بين الأجهزة

---

## أولاً: إنشاء النسخة الاحتياطية الكاملة

### 1.1 تحديد مكونات البرنامج المراد نسخها

| المكون | المسار النموذجي | ملاحظات |
|----------|----------------|---------|
| **كود التطبيق** | `/opt/app/` أو `C:\Program Files\App\` | مجلد التثبيت الكامل |
| **قاعدة البيانات** | حسب المحرك: PostgreSQL/MySQL/SQLite | استخدم `pg_dump` / `mysqldump` / نسخ ملف `.db` |
| **ملفات التكوين** | `/etc/app/` أو `C:\ProgramData\App\config\` | `config.yaml`, `.env`, `settings.json` |
| **الملفات المرفوعة/المولدة** | `/var/app/uploads/` أو `C:\AppData\uploads\` | صور، مستندات، تقارير، لوجز |
| **سجلات النظام (Logs)** | `/var/log/app/` | للتصعيد والتدقيق |
| **الشهادات/مفاتيح التشفير** | `/etc/ssl/app/` أو مخزن شهادات ويندوز | SSL، JWT secrets، مفاتيح API |
| **مهام مجدولة (Cron/Task Scheduler)** | `crontab -l` / Task Scheduler Export | نسخ أوامر الـ cron أو مهام ويندوز |
| **متغيرات البيئة** | `.env` أو سجل ويندوز | `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` |

### 1.2 سكريبت النسخ الاحتياطي الآلي (Linux/macOS)

```bash
#!/bin/bash
# backup_full.sh
BACKUP_DIR="/backup/app_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 1. كود التطبيق
tar -czf "$BACKUP_DIR/app_code.tar.gz" /opt/app --exclude="__pycache__" --exclude="*.pyc" --exclude="venv" --exclude=".git"

# 2. قاعدة البيانات (PostgreSQL مثال)
pg_dump -U postgres -h localhost -Fc -f "$BACKUP_DIR/db.dump" app_database

# 3. ملفات التكوين
tar -czf "$BACKUP_DIR/config.tar.gz" /etc/app /opt/app/.env

# 4. الملفات المرفوعة
tar -czf "$BACKUP_DIR/uploads.tar.gz" /var/app/uploads

# 5. اللوجز (آخر 30 يوم)
find /var/log/app -name "*.log" -mtime -30 -exec tar -czf "$BACKUP_DIR/logs.tar.gz" {} +

# 6. مهام cron
crontab -l > "$BACKUP_DIR/crontab.txt"

# 7. متغيرات البيئة النظامية
env | grep -E "^(APP_|DB_|REDIS_|SECRET_)" > "$BACKUP_DIR/env_vars.txt"

# 8. إنشاء ملف تحقق (manifest)
cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
Backup Date: $(date)
Hostname: $(hostname)
App Version: $(cat /opt/app/VERSION 2>/dev/null || echo "unknown")
DB Size: $(du -h /var/lib/postgresql | tail -1)
Code Size: $(du -sh /opt/app | cut -f1)
Uploads Size: $(du -sh /var/app/uploads | cut -f1)
EOF

# ضغط النسخة الكاملة
tar -czf "/backup/app_full_$(date +%Y%m%d_%H%M%S).tar.gz" -C "$BACKUP_DIR" .
echo "✅ Backup completed: $BACKUP_DIR"
```

### 1.3 للويندوز (PowerShell)

```powershell
# backup_full.ps1
$BackupDir = "C:\Backups\app_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir | Out-Null

# 1. كود التطبيق
Compress-Archive -Path "C:\Program Files\App\*" -DestinationPath "$BackupDir\app_code.zip" -CompressionLevel Optimal

# 2. قاعدة البيانات (SQL Server مثال)
sqlcmd -S localhost -Q "BACKUP DATABASE AppDB TO DISK='$BackupDir\db.bak' WITH FORMAT, INIT, COMPRESSION"

# 3. التكوين
Copy-Item "C:\ProgramData\App\config\*" "$BackupDir\config\" -Recurse

# 4. الملفات المرفوعة
Compress-Archive -Path "C:\AppData\uploads\*" -DestinationPath "$BackupDir\uploads.zip"

# 5. Task Scheduler
schtasks /Query /TN "AppTasks" /XML > "$BackupDir\tasks.xml"

# 6. متغيرات البيئة
[Environment]::GetEnvironmentVariables("Machine") | Where-Object {$_.Name -match "^(APP_|DB_|REDIS_|SECRET_)"} | Out-File "$BackupDir\env_vars.txt"

# Manifest
@"
Backup Date: $(Get-Date)
Hostname: $env:COMPUTERNAME
App Version: $(Get-Content "C:\Program Files\App\VERSION" -ErrorAction SilentlyContinue)
"@ | Out-File "$BackupDir\MANIFEST.txt"

Compress-Archive -Path "$BackupDir\*" -DestinationPath "C:\Backups\app_full_$(Get-Date -Format 'yyyyMMdd_HHmmss').zip"
Write-Host "✅ Backup completed: $BackupDir"
```

---

## ثانياً: متطلبات الجهاز الجديد

### 2.1 متطلبات النظام الدنيا

| المكون | الحد الأدنى | الموصى به |
|---------|-------------|-----------|
| **نظام التشغيل** | Ubuntu 22.04 LTS / Windows Server 2022 / Windows 11 Pro | أحدث إصدار LTS |
| **المعالج** | 2 vCPU | 4+ vCPU |
| **الذاكرة (RAM)** | 4 GB | 8-16 GB |
| **التخزين** | 50 GB SSD | 100+ GB NVMe |
| **الشبكة** | 1 Gbps | 10 Gbps داخلي |

### 2.2 التبعيات البرمجية (Dependencies)

```bash
# Ubuntu/Debian - تثبيت الحزم الأساسية
sudo apt update && sudo apt install -y \
    python3.12 python3.12-venv python3.12-dev \
    postgresql-16 postgresql-client-16 \
    redis-server \
    nginx \
    supervisor \
    git curl wget unzip \
    build-essential libpq-dev \
    certbot python3-certbot-nginx

# Python packages (في البيئة الافتراضية)
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt  # أو poetry install / pipenv install
```

```powershell
# Windows - باستخدام Chocolatey أو Winget
choco install python --version=3.12.4
choco install postgresql --version=16.2
choco install redis-64
choco install nginx
choco install nssm  # لإدارة الخدمات
# أو باستخدام winget:
winget install Python.Python.3.12 PostgreSQL.PostgreSQL Microsoft.Redis Nginx.Nginx
```

### 2.3 حسابات وصلاحيات

```bash
# إنشاء مستخدم تطبيق مخصص (Linux)
sudo useradd -r -m -s /bin/bash -d /opt/app appuser
sudo usermod -aG sudo appuser  # إذا احتاج صلاحيات محددة

# إعداد PostgreSQL
sudo -u postgres psql <<EOF
CREATE USER appuser WITH PASSWORD 'strong_random_password';
CREATE DATABASE appdb OWNER appuser;
GRANT ALL PRIVILEGES ON DATABASE appdb TO appuser;
EOF

# إعداد المجلدات
sudo mkdir -p /opt/app /var/app/uploads /var/log/app /etc/app
sudo chown -R appuser:appuser /opt/app /var/app /var/log/app /etc/app
```

---

## ثالثاً: خطوات التثبيت والاستعادة على الجهاز الجديد

### 3.1 تهيئة البيئة

```bash
# 1. نسخ ملفات النسخة الاحتياطية
scp user@old-server:/backup/app_full_20250715_143000.tar.gz /tmp/
tar -xzf /tmp/app_full_*.tar.gz -C /tmp/restore/

# 2. استعادة كود التطبيق
sudo rm -rf /opt/app/*
sudo tar -xzf /tmp/restore/app_code.tar.gz -C /
sudo chown -R appuser:appuser /opt/app

# 3. إنشاء البيئة الافتراضية
cd /opt/app
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2 استعادة قاعدة البيانات

```bash
# PostgreSQL
sudo -u postgres pg_restore -U appuser -d appdb -v /tmp/restore/db.dump

# أو MySQL
mysql -u appuser -p appdb < /tmp/restore/db.sql

# SQLite
cp /tmp/restore/app.db /opt/app/instance/app.db
```

### 3.3 استعادة التكوين والملفات

```bash
# ملفات التكوين
sudo tar -xzf /tmp/restore/config.tar.gz -C /
sudo chown -R appuser:appuser /etc/app /opt/app/.env

# الملفات المرفوعة
sudo tar -xzf /tmp/restore/uploads.tar.gz -C /
sudo chown -R appuser:appuser /var/app/uploads

# متغيرات البيئة
sudo cp /tmp/restore/env_vars.txt /etc/app/env_vars.txt
source /etc/app/env_vars.txt  # أو أضفها لـ /etc/environment
```

### 3.4 إعداد الخدمات (Systemd / Nginx / Supervisor)

```ini
# /etc/systemd/system/app.service
[Unit]
Description=My Accounting App
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=exec
User=appuser
Group=appuser
WorkingDirectory=/opt/app
Environment=PATH=/opt/app/venv/bin
EnvironmentFile=/etc/app/.env
ExecStart=/opt/app/venv/bin/gunicorn --config gunicorn.conf.py wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=app

# أمن
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/opt/app /var/app/uploads /var/log/app

[Install]
WantedBy=multi-user.target
```

```nginx
# /etc/nginx/sites-available/app
upstream app_backend {
    server unix:/opt/app/gunicorn.sock fail_timeout=0;
    # أو server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name app.yourdomain.com;  # ← سيتم تغييره في القسم الرابع
    
    client_max_body_size 50M;
    
    location /static/ {
        alias /opt/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /var/app/uploads/;
        expires 30d;
    }
    
    location / {
        proxy_pass http://app_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
```

```bash
# تفعيل الخدمات
sudo ln -sf /etc/nginx/sites-available/app /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl daemon-reload
sudo systemctl enable --now app
sudo systemctl enable --now postgresql redis nginx
```

### 3.5 استعادة المهام المجدولة

```bash
# Linux - Cron
sudo -u appuser crontab /tmp/restore/crontab.txt

# Windows - Task Scheduler
schtasks /Create /XML "C:\Restored\tasks.xml" /TN "AppTasks"
```

### 3.6 تشغيل وفحص أولي

```bash
# تطبيق migrations (إذا كان Django/Falcon/FastAPI مع Alembic)
cd /opt/app && source venv/bin/activate
python manage.py migrate  # Django
# أو: alembic upgrade head  # SQLAlchemy

# تجميع الملفات الثابتة
python manage.py collectstatic --noinput  # Django

# اختبار التشغيل
curl -f http://127.0.0.1:8000/health/ || echo "❌ Health check failed"
sudo systemctl status app
journalctl -u app -f  # متابعة اللوجز
```

---

## رابعاً: تغيير عنوان IP / النطاق

### 4.1 أماكن تخزين عنوان IP/النطاق

| الملف/المكان | المفاتيح المتوقعة | مثال |
|--------------|------------------|------|
| **ملف .env** | `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `BASE_URL` | `ALLOWED_HOSTS=app.newdomain.com,192.168.1.100` |
| **settings.py / config.py** | `ALLOWED_HOSTS`, `CORS_ORIGINS`, `SERVER_NAME` | `ALLOWED_HOSTS = ['app.newdomain.com']` |
| **nginx.conf** | `server_name` | `server_name app.newdomain.com;` |
| **قاعدة البيانات** | جداول: `sites`, `tenants`, `company_settings` | `UPDATE sites SET domain='app.newdomain.com';` |
| **SSL/شهادات** | مسارات الشهادات في nginx/systemd | `/etc/letsencrypt/live/app.newdomain.com/` |
| **Docker/Compose** | `environment:` في `docker-compose.yml` | `- ALLOWED_HOSTS=app.newdomain.com` |
| **Kubernetes** | `ConfigMap`, `Ingress` hosts | `host: app.newdomain.com` |
| **Frontend (JS/React/Vue)** | `API_BASE_URL`, `VITE_API_URL` | `const API_BASE = 'https://app.newdomain.com/api'` |

### 4.2 سكريبت تغيير IP/النطاق الآلي

```bash
#!/bin/bash
# change_domain.sh
OLD_DOMAIN="app.olddomain.com"
OLD_IP="192.168.1.50"
NEW_DOMAIN="app.newdomain.com"
NEW_IP="10.0.5.25"

echo "🔄 تغيير النطاق من $OLD_DOMAIN إلى $NEW_DOMAIN"

# 1. ملفات التكوين النصية
find /opt/app /etc/app /etc/nginx -type f \( -name "*.py" -o -name "*.yaml" -o -name "*.yml" -o -name "*.conf" -o -name "*.env" -o -name "*.json" -o -name "*.ini" \) \
    -exec sed -i "s|$OLD_DOMAIN|$NEW_DOMAIN|g; s|$OLD_IP|$NEW_IP|g" {} +

# 2. قاعدة البيانات (PostgreSQL)
sudo -u postgres psql -d appdb <<EOF
UPDATE django_site SET domain='$NEW_DOMAIN', name='$NEW_DOMAIN' WHERE domain='$OLD_DOMAIN';
UPDATE company_settings SET api_base_url='https://$NEW_DOMAIN/api' WHERE api_base_url LIKE '%$OLD_DOMAIN%';
UPDATE tenants SET domain='$NEW_DOMAIN' WHERE domain='$OLD_DOMAIN';
-- جداول أخرى محتملة
EOF

# 3. تجديد شهادة SSL (Let's Encrypt)
sudo certbot --nginx -d $NEW_DOMAIN --non-interactive --agree-tos -m admin@$NEW_DOMAIN --redirect

# 4. إعادة تحميل الخدمات
sudo systemctl reload nginx
sudo systemctl restart app

echo "✅ تم تغيير النطاق بنجاح"
```

### 4.3 للويندوز (PowerShell)

```powershell
$OldDomain = "app.olddomain.com"
$OldIP = "192.168.1.50"
$NewDomain = "app.newdomain.com"
$NewIP = "10.0.5.25"

# 1. استبدال في ملفات التكوين
Get-ChildItem "C:\Program Files\App", "C:\ProgramData\App\config", "C:\nginx\conf" -Recurse -File `
    -Include *.json,*.yaml,*.yml,*.conf,*.env,*.config,*.ini |
ForEach-Object {
    (Get-Content $_ -Raw) -replace [regex]::Escape($OldDomain), $NewDomain `
                           -replace [regex]::Escape($OldIP), $NewIP |
    Set-Content $_ -Encoding UTF8
}

# 2. قاعدة البيانات (SQL Server)
Invoke-Sqlcmd -ServerInstance localhost -Database AppDB -Query "
    UPDATE Sites SET Domain = '$NewDomain' WHERE Domain = '$OldDomain';
    UPDATE CompanySettings SET ApiBaseUrl = REPLACE(ApiBaseUrl, '$OldDomain', '$NewDomain');
    UPDATE Tenants SET Domain = '$NewDomain' WHERE Domain = '$OldDomain';
"

# 3. nginx
nginx -s reload
Restart-Service -Name "AppService"
```

---

## خامساً: إجراءات التحقق والاختبار

### 5.1 قائمة التحقق المنهجية (Checklist)

| # | الاختبار | الأمر/الطريقة | المعيار |
|---|----------|--------------|---------|
| **1** | **خدمة التطبيق** | `systemctl status app` | `active (running)` |
| **2** | **قاعدة البيانات** | `psql -U appuser -d appdb -c "SELECT 1;"` | استجابة `1` |
| **3** | **Redis** | `redis-cli ping` | `PONG` |
| **4** | **Nginx** | `nginx -t && systemctl status nginx` | `syntax is ok` + `active` |
| **5** | **Health Endpoint** | `curl -f https://$NEW_DOMAIN/health/` | HTTP 200 + `{"status":"ok"}` |
| **6** | **تسجيل الدخول** | متصفح / `curl -X POST /api/auth/login` | JWT token صحيح |
| **7** | **قائمة الحسابات** | `GET /api/accounts/` | JSON يحتوي بيانات |
| **8** | **إنشاء قيد** | `POST /api/journal-entries/` | HTTP 201 + قيد في DB |
| **9** | **فاتورة مبيعات** | `POST /api/sales/invoices/` | PDF يتولد، قيد يرتبط |
| **10** | **التسوية البنكية** | شاشة التسوية | تظهر الحركات غير المسواة |
| **11** | **الصلاحيات** | دخول بمستخدمين مختلفين | RBAC يعمل حسب الأدوار |
| **12** | **الملفات المرفوعة** | رفع ملف في فاتورة | يظهر في `/media/` |
| **13** | **المهام المجدولة** | `crontab -l` / Task Scheduler | تظهر المهام، `last run` حديث |
| **14** | **اللوجز** | `journalctl -u app --since "1 hour ago"` | لا توجد ERROR/CRITICAL |
| **15** | **SSL/HTTPS** | `curl -I https://$NEW_DOMAIN` | HTTP 200، شهادة صالحة |
| **16** | **النسخ الاحتياطي التلقائي** | تشغيل سكريبت النسخ | ملف في `/backup/` بحجم > 0 |

### 5.2 اختبارات التكامل الآلية (Smoke Tests)

```python
# tests/smoke_test.py
import requests
import sys

BASE = "https://app.newdomain.com"
TOKEN = None

def test_health():
    r = requests.get(f"{BASE}/health/", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("✅ Health check passed")

def test_login():
    global TOKEN
    r = requests.post(f"{BASE}/api/auth/login/", json={
        "username": "admin", "password": "testpass123"
    }, timeout=10)
    assert r.status_code == 200
    TOKEN = r.json()["access"]
    print("✅ Login passed")

def test_accounts_list():
    r = requests.get(f"{BASE}/api/accounts/", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert len(r.json()["results"]) > 0
    print("✅ Accounts list passed")

def test_create_journal():
    r = requests.post(f"{BASE}/api/journal-entries/", headers={"Authorization": f"Bearer {TOKEN}"}, json={
        "entry_type": "general", "date": "2025-07-15",
        "description": "Smoke test entry",
        "lines": [
            {"account": 1110, "debit": 100, "credit": 0},
            {"account": 4000, "debit": 0, "credit": 100}
        ]
    })
    assert r.status_code == 201
    print("✅ Journal creation passed")

if __name__ == "__main__":
    try:
        test_health()
        test_login()
        test_accounts_list()
        test_create_journal()
        print("\n🎉 All smoke tests PASSED")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        sys.exit(1)
```

```bash
# تشغيل الاختبارات
cd /opt/app && source venv/bin/activate
python tests/smoke_test.py
```

### 5.3 مراقبة ما بعد النشر (أول 24-48 ساعة)

```bash
# 1. مراقبة اللوجز في الوقت الفعلي
journalctl -u app -f --since "1 hour ago" | grep -E "(ERROR|CRITICAL|WARNING)"

# 2. مراقبة أداء قاعدة البيانات
sudo -u postgres psql -d appdb -c "
SELECT query, calls, mean_exec_time, rows 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC LIMIT 10;"

# 3. مراقبة استخدام الموارد
htop  # أو: watch -n 5 'ps aux | grep -E "(gunicorn|postgres|redis|nginx)"'

# 4. التحقق من النسخ الاحتياطي الليلي
ls -lh /backup/app_full_$(date +%Y%m%d)*

# 5. اختبار استعادة من النسخة الاحتياطية (في بيئة اختبار منفصلة)
# مهم: جرب استعادة النسخة في VM منفصل للتأكد من صلاحيتها
```

---

## ملخص سريع للأمر الحاسم

```bash
# على الجهاز القديم - إنشاء النسخة
tar -czf backup.tar.gz /opt/app /etc/app /var/app/uploads && pg_dump -Fc db > db.dump

# على الجهاز الجديد - استعادة سريعة
tar -xzf backup.tar.gz -C / && pg_restore -d appdb db.dump && systemctl restart app nginx
```

---

## نصائح ذهبية

| النصيحة | السبب |
|----------|--------|
| **اختبر الاستعادة في بيئة منفصلة أولاً** | تجنب المفاجآت على الإنتاج |
| **وثق كل متغير بيئة في ملف `.env.example`** | يسهل النشر المستقبلي |
| **استخدم Infrastructure as Code (Ansible/Terraform)** | يجعل العملية قابلة للتكرار |
| **احتفظ بنسخة من الشهادات SSL ومفاتيح التشفير منفصلة** | أمان، ولا تُنسخ مع الكود |
| **أتمت عملية التحقق (Smoke Tests) في CI/CD** | يكتشف الكسر فوراً |
| **خطط لـ Rollback قبل البدء** | `systemctl stop app && tar -xzf pre_migration_backup.tar.gz` |

---

## مسارات الملفات المهمة للمراجعة السريعة

```
📁 /opt/app/                 # كود التطبيق
📁 /etc/app/                 # ملفات التكوين
📁 /var/app/uploads/         # الملفات المرفوعة
📁 /var/log/app/             # سجلات التطبيق
📁 /backup/                  # النسخ الاحتياطية
📄 /opt/app/.env             # متغيرات البيئة
📄 /etc/nginx/sites-available/app  # إعدادات Nginx
📄 /etc/systemd/system/app.service # خدمة Systemd
📄 /tmp/restore/MANIFEST.txt # manifiest النسخة الاحتياطية
```

---

*تم إنشاء هذا الدليل بتاريخ: 2025-07-15*
*للاستفسارات: توثيق العملية في ويكي الفريق أو نظام إدارة المعرفة*