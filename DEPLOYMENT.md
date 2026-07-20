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
