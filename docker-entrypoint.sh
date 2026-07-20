#!/bin/sh
# docker-entrypoint.sh — يُنفَّذ داخل الحاوية عند الإقلاع.
# يتأكد من توفّر متغيّرات الإنتاج ثم يهيّئ قاعدة البيانات ويشغّل الخادم.
set -e

if [ -z "$DJANGO_SECRET_KEY" ]; then
  echo "ERROR: DJANGO_SECRET_KEY is required. Set it in your .env file." >&2
  exit 1
fi

echo "==> Applying database migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Starting Gunicorn on 0.0.0.0:8012 ..."
exec gunicorn accounting_system.wsgi:application \
    --bind 0.0.0.0:8012 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 120
