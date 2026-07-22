import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, '.env'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'accounting_system.settings')

import django

django.setup()
from django.core.management import call_command

port = os.environ.get('DJANGO_BIND_PORT', '8001')
print('=' * 50, flush=True)
print('  Accounting System - Starting...', flush=True)
print(f'  Open: http://127.0.0.1:{port}', flush=True)
print(f'  Admin: http://127.0.0.1:{port}/admin/', flush=True)
print('  User: admin / admin123', flush=True)
print('=' * 50, flush=True)
call_command('runserver', f'0.0.0.0:{port}')
