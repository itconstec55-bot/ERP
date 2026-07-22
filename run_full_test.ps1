@(
    'cd D:\accounting_system',
    '.venv\\Scripts\\Activate.ps1',
    '$env:DJANGO_SECRET_KEY = "test-key"',
    '$env:DJANGO_DEBUG = "True"',
    '$env:DJANGO_SETTINGS_MODULE = "accounting_system.settings"',
    'ruff check . --fix --quiet',
    'ruff format .',
    'python -m pytest --cov=. --cov-report=term --tb=short -o timeout=60 -q -k "not test_utils_middleware" --maxfail=10'
) | % { $_ -ForegroundColor White }
