@echo off
REM ===========================================================================
REM deploy/start_backend.bat - Run Django behind Gunicorn on localhost
REM ===========================================================================
REM Run this first, then start Nginx with deploy/nginx_dual.conf.
REM Edit port to match proxy_pass in nginx (default: 127.0.0.1:8012).
REM To stop: Ctrl+C then close the window.

cd /d "%~dp0"

set DJANGO_DEBUG=false
set DJANGO_SECRET_KEY=CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY
set DJANGO_ALLOWED_HOSTS=192.168.1.31,196.218.24.45,127.0.0.1,localhost

python -m gunicorn accounting_system.wsgi:application ^
    --bind 127.0.0.1:8012 ^
    --workers 3 ^
    --timeout 120 ^
    --access-logfile - ^
    --error-logfile -

REM Linux equivalent:
REM gunicorn accounting_system.wsgi:application --bind 127.0.0.1:8012 --workers 3
