# DEPLOYMENT.md - Accounting System Deployment Guide

## Overview

Three deployment methods, ordered by ease of use:

| Method | Best For | Requirements | Difficulty |
|--------|----------|--------------|------------|
| **ZIP + install.bat** | Windows end users | Python 3.10+ | Easy |
| **Docker** | Cross-platform, teams | Docker Desktop | Medium |
| **PyInstaller EXE** | Standalone distribution | PyInstaller | Hard |

---

## Method 1: ZIP Package (Recommended for most users)

### Build the package

```bash
python build_package.py --format zip
```

Output: `dist/AccountingSystem_v1.0.0_<timestamp>.zip`

### Install on target machine

1. Extract the ZIP to any folder
2. Double-click `install.bat`
3. Wait for installation to complete
4. Double-click `start.bat`
5. Open browser: http://127.0.0.1:8000

Default login: `admin` / `admin123`

### What install.bat does

- Checks Python installation
- Creates virtual environment (`venv/`)
- Installs all dependencies
- Generates `.env` with secret key
- Runs database migrations
- Seeds chart of accounts (57 accounts)
- Creates admin user
- Collects static files

---

## Method 2: Docker

### Build and run

```bash
docker-compose up -d
```

Or build image manually:

```bash
docker build -t accounting-system .
docker run -p 8000:8000 accounting-system
```

### Volumes (persistent data)

- `db_data` - SQLite database
- `media_data` - Uploaded files
- `backup_data` - Backups
- `logs_data` - Logs

### Stop

```bash
docker-compose down
```

### View logs

```bash
docker-compose logs -f app
```

---

## Method 3: PyInstaller EXE

### Build

```bash
pip install pyinstaller
python build_package.py --format exe
```

Output: `dist/exe/AccountingSystem/AccountingSystem.exe`

### Inno Setup Installer

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Build EXE first: `python build_package.py --format exe`
3. Build installer: `python build_package.py --format inno`
4. Output: `dist/AccountingSystemSetup.exe`

---

## Method 4: Linux/Mac Manual

```bash
chmod +x setup.sh
./setup.sh
./start.sh
```

---

## Environment Variables

Create `.env` file in project root:

```env
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,your-domain.com
```

Optional:
```env
WHATSAPP_APP_ID=...
WHATSAPP_APP_SECRET=...
WHATSAPP_PHONE_ID=...
WHATSAPP_API_TOKEN=...
```

---

## Production Recommendations

### Security

1. Change default admin password immediately
2. Set `DJANGO_DEBUG=False`
3. Use HTTPS (reverse proxy: nginx/caddy)
4. Set `DJANGO_SECRET_KEY` to a random value
5. Restrict `DJANGO_ALLOWED_HOSTS`

### Performance

1. Use `gunicorn` instead of `runserver`:
   ```bash
   pip install gunicorn
   gunicorn accounting_system.wsgi:application -b 0.0.0.0:8000 -w 2
   ```

2. For high traffic, add nginx as reverse proxy

### Backup

- Automated: `start_service.bat` runs backups every 2 hours
- Manual: Go to Settings > Backup in the app
- Database: `db.sqlite3` file (copy it)
- Files: `media/` directory

### Monitoring

- Health check: `python deployment/health_check.py`
- Service status: `python deployment/service.py status`
- Logs: `logs/accounting.log`, `logs/errors.log`

---

## Build All Formats

```bash
python build_package.py --clean --with-data
```

This creates:
- `dist/AccountingSystem_v1.0.0_*.zip` - Portable package
- `dist/exe/AccountingSystem/` - Standalone EXE
- Docker image: `accounting-system:latest`

---

## Troubleshooting

### "Python not found"
Install Python 3.10+ from https://python.org and add to PATH.

### "Port 8000 already in use"
Another process is using port 8000. Either stop it or change the port:
```bash
python run_server.py  # Edit run_server.py to change port
```

### "Database is locked"
Close all instances of the application, then delete `db.sqlite3-wal` and `db.sqlite3-shm`.

### "ModuleNotFoundError"
Reinstall dependencies:
```bash
pip install -r requirements.txt
```

---

## Method 5: Automated CI/CD Deployment (GitHub Actions → Docker on a Linux server)

The repository includes `.github/workflows/ci.yml` which, on every push to `main`/`develop`, runs lint + tests, builds static files, then deploys via SSH using Docker Compose. Deployment is **skipped automatically** if the deploy secrets are not configured (the pipeline stays green).

### Required GitHub repository secrets (Settings → Secrets and variables → Actions)
| Secret | Value |
|--------|-------|
| `DEPLOY_HOST` | Public IP or hostname of the Linux server |
| `DEPLOY_USER` | SSH user on the server (e.g. `deploy`) |
| `DEPLOY_SSH_KEY` | Full private key (`-----BEGIN OPENSSH PRIVATE KEY-----` … `-----END…-----`) |
| `DEPLOY_PORT` | Optional, default `22` |
| `DEPLOY_PATH` | Optional, default `~/erp` |

### Prepare the server once
Use the provided script `deploy/server_setup.sh` (run as root on Ubuntu 22.04+). It installs Docker, creates the `deploy` user, generates the SSH deploy key (print its private part into `DEPLOY_SSH_KEY`), clones the repo to `~/erp`, and writes a starter `.env`.

```bash
sudo bash deploy/server_setup.sh
cat /home/deploy/.ssh/erp_deploy_key   # copy this into GitHub secret DEPLOY_SSH_KEY
# then edit /home/deploy/erp/.env and set a strong DJANGO_SECRET_KEY
```

### What the deploy step runs on the server
```bash
cd ~/erp
git pull --ff-only origin main        # or develop
docker compose pull
docker compose up -d --build
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py collectstatic --noinput
docker compose ps
```

### Local verification (no remote server required)
The deploy path was verified locally by running the same steps Django-side:
```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
# with DJANGO_DEBUG=false and a strong DJANGO_SECRET_KEY
python manage.py runserver 127.0.0.1:8012
# /monitoring/ and /accounts/login/ both return HTTP 200
```
Note: `gunicorn` only runs inside the Linux container (it imports Unix-only `fcntl`); the Dockerfile handles this correctly.
