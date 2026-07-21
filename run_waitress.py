"""Production server on Windows via Waitress (WSGI production server).

Reads .env file automatically via python-dotenv.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv(BASE_DIR / '.env')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'accounting_system.settings')
os.environ.setdefault('DJANGO_DEBUG', 'false')

if not os.environ.get('DJANGO_SECRET_KEY'):
    raise SystemExit('DJANGO_SECRET_KEY is missing - edit .env before running.')

from waitress import serve

from accounting_system.wsgi import application

port = int(os.environ.get('BIND_PORT', '8001'))
host = os.environ.get('DJANGO_BIND_HOST', '0.0.0.0')  # noqa: S104
print(f'==> Production server (waitress) on http://{host}:{port}  [DEBUG={os.environ.get("DJANGO_DEBUG")}]')
serve(application, host=host, port=port, threads=8)
