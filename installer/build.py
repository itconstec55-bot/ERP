"""
Build script for AccountingSystem
Creates a standalone executable using PyInstaller
"""
import os
import sys
import shutil
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(PROJECT_ROOT, 'installer', 'dist')
BUILD_DIR = os.path.join(PROJECT_ROOT, 'installer', 'build')
SPEC_FILE = os.path.join(PROJECT_ROOT, 'installer', 'build.spec')


def clean():
    print("Cleaning previous builds...")
    for d in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
    print("Clean complete.")


def build():
    print("Building AccountingSystem executable...")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Spec file: {SPEC_FILE}")

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        '--distpath', DIST_DIR,
        '--workpath', BUILD_DIR,
        SPEC_FILE,
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        print("\nBuild successful!")
        exe_path = os.path.join(DIST_DIR, 'AccountingSystem', 'AccountingSystem.exe')
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"Executable: {exe_path}")
            print(f"Size: {size_mb:.1f} MB")
    else:
        print(f"\nBuild failed with return code: {result.returncode}")
        sys.exit(1)


def create_launcher():
    """Create a batch launcher for the exe"""
    launcher_content = '''@echo off
title Accounting System
echo Starting Accounting System...
echo.
echo The system will start on http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
echo.
start http://127.0.0.1:8000
"AccountingSystem.exe" runserver 0.0.0.0:8000 --noreload
pause
'''
    launcher_path = os.path.join(DIST_DIR, 'AccountingSystem', 'تشغيل النظام.bat')
    with open(launcher_path, 'w', encoding='utf-8') as f:
        f.write(launcher_content)
    print(f"Launcher created: {launcher_path}")


def create_readme():
    """Create a README for the distribution"""
    readme_content = '''# نظام المحاسبة المتكامل

## التشغيل
1. اضغط مرتين على "AccountingSystem.exe"
2. افتح المتصفح على: http://127.0.0.1:8000
3. تسجيل الدخول: admin / admin123

## البيانات الأولية
النظام يأتي مع بيانات تجريبية جاهزة.

## النسخ الاحتياطي
اذهب إلى: الإعدادات > النسخ الاحتياطي

## الربط والمزامنة
اذهب إلى: الإعدادات > الربط والمزامنة

## الدعم
لأي مشاكل، تواصل مع المطور.
'''
    readme_path = os.path.join(DIST_DIR, 'AccountingSystem', 'README.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"README created: {readme_path}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'clean':
        clean()
    else:
        clean()
        build()
        create_launcher()
        create_readme()
        print("\nBuild complete! Check installer/dist/AccountingSystem/")
