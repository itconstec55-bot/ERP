import io
import os
import sys
import time

os.environ['DJANGO_SETTINGS_MODULE'] = 'accounting_system.settings'
_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE)

import django

django.setup()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from common.dummy_generator import DummyDataGenerator


def progress(msg):
    print(msg, flush=True)


t0 = time.time()
gen = DummyDataGenerator(profile='tiny', clear_first=True, progress_callback=progress)
gen.generate()
print(f'\nTotal time: {time.time() - t0:.1f}s', flush=True)
