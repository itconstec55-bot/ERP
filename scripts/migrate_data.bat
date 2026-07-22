@echo off
REM ============================================================
REM  Migrate data from SQLite to PostgreSQL
REM  Run after: docker compose up -d --build (Postgres on 127.0.0.1:5433)
REM ============================================================
cd /d "%~dp0"

set DJANGO_SETTINGS_MODULE=accounting_system.settings
set DJANGO_DEBUG=false
set DJANGO_DB_PASSWORD=ChangeMeStrongPassword123!
set DJANGO_SECRET_KEY=__MIGRATION_TEMP_KEY__

echo [1/4] Exporting data from SQLite...
set DJANGO_DB_ENGINE=sqlite
python manage.py dumpdata --natural-foreign --natural-primary ^
  --exclude contenttypes --exclude auth.permission ^
  --exclude sessions --exclude admin.LogEntry ^
  --indent 2 -o data_dump.json
if errorlevel 1 ( echo [ERROR] Export failed & pause & exit /b 1 )
echo [OK] Exported to data_dump.json

echo [2/4] Building schema on PostgreSQL...
set DJANGO_DB_ENGINE=postgres
set DJANGO_DB_HOST=127.0.0.1
set DJANGO_DB_PORT=5433
set DJANGO_DB_NAME=accounting
set DJANGO_DB_USER=accounting
python manage.py migrate --noinput
if errorlevel 1 ( echo [ERROR] Migrate failed & pause & exit /b 1 )
echo [OK] Schema built

echo [3/4] Loading data into PostgreSQL...
python manage.py loaddata data_dump.json
if errorlevel 1 ( echo [ERROR] Load failed & pause & exit /b 1 )
echo [OK] Data loaded

echo [4/4] Updating sequences...
python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"SELECT 'SELECT setval(pg_get_serial_sequence('||quote_literal(tbl)||','||quote_literal(col)||'), (SELECT MAX('||col||') FROM '||tbl||')+1 FROM '||tbl||');' FROM (SELECT t.relname AS tbl, a.attname AS col FROM pg_class t JOIN pg_attribute a ON a.attrelid=t.oid JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.atthasdef AND pg_get_expr(d.adbin,d.adrelid) LIKE 'nextval%') s;\"); "
echo [DONE] Migration complete.
pause
