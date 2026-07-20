"""
run_multi.py — مُشغِّل متعدد الربط (Multi-bind launcher)

يقرأ قائمة العناوين من إعداد SERVER_BIND_HOSTS (عبر متغيّر DJANGO_BIND_HOSTS)
والمنفذ من SERVER_BIND_PORT (عبر DJANGO_BIND_PORT)، ثم يُشغِّل عملية Django
runserver منفصلة لكل عنوان بحيث يربط كل واجهة شبكة على حدة.

المزايا:
- ربط حقيقي بعناوين محددة (ليس 0.0.0.0) إن كانت مُسندة للواجهات.
- إضافة عنوان جديد = إضافته للقائمة وتشغيل نسخة واحدة فقط دون إيقاف الباقي.
- كل نسخة مستقلة، فتعطّل واحدة لا يؤثر على الأخرى.

ملاحظة: للإنتاج يُفضَّل Nginx كوكيل عكسي (انظر deploy/nginx_dual.conf) مع
gunicorn على 127.0.0.1، أمّا هذا الملف فللتشغيل المباشر والسريع.

الاستخدام:
    python run_multi.py
    DJANGO_BIND_HOSTS=192.168.1.31,10.0.0.5 DJANGO_BIND_PORT=8012 python run_multi.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Load .env file
env_path = BASE_DIR / '.env'
if env_path.exists():
    for raw in env_path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        os.environ.setdefault(key.strip(), val.strip())

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'accounting_system.settings')
django.setup()

from django.conf import settings

HOSTS = list(settings.SERVER_BIND_HOSTS)
PORT = settings.SERVER_BIND_PORT
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    if not HOSTS:
        print('[run_multi] لا توجد عناوين ربط مُعرّفة (SERVER_BIND_HOSTS).', file=sys.stderr)
        sys.exit(1)

    procs = []
    for host in HOSTS:
        addr = f'{host}:{PORT}'
        print(f'[run_multi] >> تشغيل الخادم على {addr}')
        p = subprocess.Popen(
            [sys.executable, 'manage.py', 'runserver', '--noreload', addr],
            cwd=BASE_DIR,
        )
        procs.append((addr, p))

    print(f'[run_multi] تم تشغيل {len(procs)} نسخة. Ctrl+C للإيقاف.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n[run_multi] إيقاف النسخ...')
        for addr, p in procs:
            if p.poll() is None:
                p.terminate()
        for addr, p in procs:
            p.wait()


if __name__ == '__main__':
    main()
