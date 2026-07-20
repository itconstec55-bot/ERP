import os, re, glob

ROOT = r'J:\2027\accounting_system'
skip = {'accounting_system', 'tests', 'deploy', 'deployment', 'dist', 'static',
        'staticfiles', 'media', 'logs', 'installer', 'backups_storage'}

rows = []
for views_path in glob.glob(os.path.join(ROOT, '*', 'views.py')):
    app = os.path.basename(os.path.dirname(views_path))
    if app in skip:
        continue
    text = open(views_path, encoding='utf-8').read().splitlines()
    pending = []  # decorators above a def
    for line in text:
        s = line.strip()
        m = re.match(r'@(permission_required_or_login|permission_required|login_required|csrf_exempt|require_GET|require_POST|require_http_methods)\s*(\(([^)]*)\))?', s)
        if s.startswith('@'):
            if m:
                pending.append((m.group(1), (m.group(3) or '').strip()))
            else:
                pending.append((s[1:].split('(')[0], ''))
            continue
        fn = re.match(r'def\s+(\w+)\s*\(', s)
        if fn:
            name = fn.group(1)
            perm = access = '— (عام/بلا قيد)'
            for dec, arg in pending:
                if dec == 'permission_required_or_login':
                    access = f"صلاحية: {arg}" if arg else 'صلاحية مطلوبة'
                elif dec == 'permission_required':
                    access = f"صلاحية: {arg}" if arg else 'صلاحية مطلوبة'
                elif dec == 'login_required':
                    access = 'دخول فقط (مصادقة)'
                elif dec == 'csrf_exempt':
                    access = 'csrf_exempt'
                elif dec in ('require_GET', 'require_POST', 'require_http_methods'):
                    access = f'قيد طريقة HTTP: {dec}'
            rows.append((app, name, access))
            pending = []

out = []
out.append('| التطبيق (App) | الشاشة/الدالة (View) | مستوى الوصول / الصلاحية المطلوبة |')
out.append('|---|---|---|')
for app, name, access in rows:
    out.append(f'| `{app}` | `{name}` | {access} |')

open(os.path.join(ROOT, 'docs', 'permissions_matrix.md'), 'w', encoding='utf-8').write('\n'.join(out))
print(f'TOTAL views scanned: {len(rows)}')
print('\n'.join(out[:12]))
