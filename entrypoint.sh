#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --no-input

echo "Collecting static files..."
python manage.py collectstatic --no-input 2>/dev/null || true

echo "Starting server..."
exec "$@"
