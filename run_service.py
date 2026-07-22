"""
Launcher: Start the full accounting system service.
Double-click this file or run: python run_service.py
"""

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

if __name__ == '__main__':
    os.chdir(BASE_DIR)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'accounting_system.settings'
    cmd = [PYTHON, os.path.join(BASE_DIR, 'deployment', 'service.py')]
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    subprocess.run(cmd, cwd=BASE_DIR)
