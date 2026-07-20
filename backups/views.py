import os
import shutil
import subprocess
import zipfile
import tempfile
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.http import FileResponse
from django.conf import settings
from .models import Backup, BackupSettings, FactoryResetRequest
from .forms import BackupSettingsForm
from common.permissions import screen_permission_required
from . import factory_reset as fr
import logging

logger = logging.getLogger('accounting')

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups_storage')


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _format_size(size_bytes):
    if size_bytes < 1024:
        return f'{size_bytes} B'
    elif size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.1f} KB'
    elif size_bytes < 1024 * 1024 * 1024:
        return f'{size_bytes / (1024 * 1024):.1f} MB'
    else:
        return f'{size_bytes / (1024 * 1024 * 1024):.2f} GB'


def _safe_extract_zip(zip_file, dest_dir):
    """Extract zip safely, preventing path traversal attacks."""
    for info in zip_file.infolist():
        target_path = os.path.realpath(os.path.join(dest_dir, info.filename))
        dest_real = os.path.realpath(dest_dir)
        if not target_path.startswith(dest_real):
            raise ValueError(f'مسار غير آمن في الملف المضغوط: {info.filename}')
    zip_file.extractall(dest_dir)


@login_required
def backup_dashboard(request):
    _ensure_backup_dir()
    backups = Backup.objects.all()[:50]
    backup_settings = BackupSettings.get_settings()

    total_size = sum(b.file_size for b in Backup.objects.filter(status='completed'))
    db_path = str(settings.DATABASES['default']['NAME'])
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    media_size = 0
    if os.path.exists(settings.MEDIA_ROOT):
        for root, dirs, files in os.walk(settings.MEDIA_ROOT):
            for f in files:
                media_size += os.path.getsize(os.path.join(root, f))

    context = {
        'backups': backups,
        'backup_settings': backup_settings,
        'total_backups_count': Backup.objects.count(),
        'total_backups_size': _format_size(total_size),
        'db_size': _format_size(db_size),
        'media_size': _format_size(media_size),
        'data_size': _format_size(db_size + media_size),
    }
    return render(request, 'backups/backup_dashboard.html', context)


@login_required
@require_POST
def create_backup(request):
    _ensure_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    name = request.POST.get('name', f'نسخة_{timestamp}')
    backup_type = request.POST.get('backup_type', 'data')

    backup = Backup.objects.create(
        name=name,
        backup_type=backup_type,
        file_path='',
        status='pending',
        created_by=request.user,
    )

    try:
        if backup_type == 'data':
            filename = f'data_backup_{timestamp}.zip'
            filepath = os.path.join(BACKUP_DIR, filename)
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                db_path = str(settings.DATABASES['default']['NAME'])
                zf.write(db_path, 'db.sqlite3')
                if os.path.exists(db_path + '-wal'):
                    zf.write(db_path + '-wal', 'db.sqlite3-wal')
                if os.path.exists(db_path + '-shm'):
                    zf.write(db_path + '-shm', 'db.sqlite3-shm')
                if os.path.exists(settings.MEDIA_ROOT):
                    for root, dirs, files in os.walk(settings.MEDIA_ROOT):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, settings.MEDIA_ROOT)
                            zf.write(file_path, os.path.join('media', arcname))

        elif backup_type == 'json':
            filename = f'dump_{timestamp}.json'
            filepath = os.path.join(BACKUP_DIR, filename)
            result = subprocess.run(
                [settings.BASE_DIR / 'manage.py', 'dumpdata',
                 '--indent', '2', '--exclude', 'auth.permission', '--exclude', 'contenttypes'],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                raise Exception(f'dumpdata failed: {result.stderr}')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result.stdout)

        elif backup_type == 'full':
            filename = f'full_backup_{timestamp}.zip'
            filepath = os.path.join(BACKUP_DIR, filename)
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                db_path = str(settings.DATABASES['default']['NAME'])
                zf.write(db_path, 'db.sqlite3')
                if os.path.exists(db_path + '-wal'):
                    zf.write(db_path + '-wal', 'db.sqlite3-wal')
                if os.path.exists(db_path + '-shm'):
                    zf.write(db_path + '-shm', 'db.sqlite3-shm')

                if os.path.exists(settings.MEDIA_ROOT):
                    for root, dirs, files in os.walk(settings.MEDIA_ROOT):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, settings.BASE_DIR)
                            zf.write(file_path, arcname)

                for fname in ['manage.py', 'requirements.txt']:
                    fpath = os.path.join(settings.BASE_DIR, fname)
                    if os.path.exists(fpath):
                        zf.write(fpath, fname)

        file_size = os.path.getsize(filepath)
        backup.file_path = filepath
        backup.file_size = file_size
        backup.status = 'completed'
        backup.save()

        messages.success(request, f'تم إنشاء النسخة "{name}" بنجاح ({_format_size(file_size)})')

    except Exception as e:
        backup.status = 'failed'
        backup.notes = str(e)
        backup.save()
        messages.error(request, 'فشلت العملية. يرجى المحاولة لاحقاً.')
        logger.exception('Backup operation failed')

    return redirect('backups:backup_dashboard')


@login_required
def download_backup(request, pk):
    backup = get_object_or_404(Backup, pk=pk)
    if not backup.file_path or not os.path.exists(backup.file_path):
        messages.error(request, 'ملف النسخة غير موجود')
        return redirect('backups:backup_dashboard')

    filename = os.path.basename(backup.file_path)
    return FileResponse(
        open(backup.file_path, 'rb'),
        as_attachment=True,
        filename=filename
    )


@login_required
@require_POST
def delete_backup(request, pk):
    backup = get_object_or_404(Backup, pk=pk)
    backup.delete_file()
    name = backup.name
    backup.delete()
    messages.success(request, f'تم حذف النسخة "{name}" بنجاح')
    return redirect('backups:backup_dashboard')


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/admin/')
def restore_backup(request, pk):
    backup = get_object_or_404(Backup, pk=pk, backup_type__in=['data', 'full'])

    if request.method != 'POST':
        messages.warning(request, 'اضغط "استرجاع" لتأكيد العملية')
        return redirect('backups:backup_dashboard')

    if not backup.file_path or not os.path.exists(backup.file_path):
        messages.error(request, 'ملف النسخة غير موجود')
        return redirect('backups:backup_dashboard')

    db_path = str(settings.DATABASES['default']['NAME'])
    restore_file = db_path + '.restore_backup'

    try:
        shutil.copy2(db_path, restore_file)

        if backup.backup_type == 'data':
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(backup.file_path, 'r') as zf:
                    _safe_extract_zip(zf, tmp_dir)

                extracted_db = os.path.join(tmp_dir, 'db.sqlite3')
                if os.path.exists(extracted_db):
                    shutil.copy2(extracted_db, db_path)
                    wal_file = os.path.join(tmp_dir, 'db.sqlite3-wal')
                    if os.path.exists(wal_file):
                        shutil.copy2(wal_file, db_path + '-wal')
                    shm_file = os.path.join(tmp_dir, 'db.sqlite3-shm')
                    if os.path.exists(shm_file):
                        shutil.copy2(shm_file, db_path + '-shm')

                extracted_media = os.path.join(tmp_dir, 'media')
                if os.path.exists(extracted_media):
                    for root, dirs, files in os.walk(extracted_media):
                        for file in files:
                            src = os.path.join(root, file)
                            rel = os.path.relpath(src, extracted_media)
                            dst = os.path.join(settings.MEDIA_ROOT, rel)
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            shutil.copy2(src, dst)

        elif backup.backup_type == 'full':
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(backup.file_path, 'r') as zf:
                    _safe_extract_zip(zf, tmp_dir)

                extracted_db = os.path.join(tmp_dir, 'db.sqlite3')
                if os.path.exists(extracted_db):
                    shutil.copy2(extracted_db, db_path)
                    wal_file = os.path.join(tmp_dir, 'db.sqlite3-wal')
                    if os.path.exists(wal_file):
                        shutil.copy2(wal_file, db_path + '-wal')
                    shm_file = os.path.join(tmp_dir, 'db.sqlite3-shm')
                    if os.path.exists(shm_file):
                        shutil.copy2(shm_file, db_path + '-shm')

                extracted_media = os.path.join(tmp_dir, 'media')
                if os.path.exists(extracted_media):
                    for root, dirs, files in os.walk(extracted_media):
                        for file in files:
                            src = os.path.join(root, file)
                            rel = os.path.relpath(src, extracted_media)
                            dst = os.path.join(settings.MEDIA_ROOT, rel)
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            shutil.copy2(src, dst)

        messages.success(request, f'تم استرجاع النسخة "{backup.name}" بنجاح. أعد تشغيل السيرفر.')
        backup.notes = (backup.notes + '\n' if backup.notes else '') + f'تم الاسترجاع في {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        backup.save()

    except Exception as e:
        if os.path.exists(restore_file):
            shutil.copy2(restore_file, db_path)
        messages.error(request, 'فشلت العملية. يرجى المحاولة لاحقاً.')
        logger.exception('Backup operation failed')

    return redirect('backups:backup_dashboard')


@login_required
def export_json(request):
    _ensure_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'dump_{timestamp}.json'
    filepath = os.path.join(BACKUP_DIR, filename)

    try:
        result = subprocess.run(
            [settings.BASE_DIR / 'manage.py', 'dumpdata',
             '--indent', '2', '--exclude', 'auth.permission', '--exclude', 'contenttypes'],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise Exception(f'dumpdata failed: {result.stderr}')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(result.stdout)

        file_size = os.path.getsize(filepath)
        Backup.objects.create(
            name=f'تصدير JSON - {timestamp}',
            backup_type='json',
            file_path=filepath,
            file_size=file_size,
            status='completed',
            created_by=request.user,
        )
        messages.success(request, f'تم التصدير بنجاح ({_format_size(file_size)})')
    except Exception as e:
        messages.error(request, 'فشلت العملية. يرجى المحاولة لاحقاً.')
        logger.exception('Backup operation failed')

    return redirect('backups:backup_dashboard')


@login_required
def import_json(request):
    if request.method != 'POST' or 'json_file' not in request.FILES:
        messages.error(request, 'اختر ملف JSON')
        return redirect('backups:backup_dashboard')

    uploaded = request.FILES['json_file']
    if uploaded.size > MAX_UPLOAD_SIZE:
        messages.error(request, f'حجم الملف يتجاوز الحد الأقصى ({MAX_UPLOAD_SIZE // (1024*1024)} ميجابايت)')
        return redirect('backups:backup_dashboard')
    if not uploaded.name.endswith('.json'):
        messages.error(request, 'يجب أن يكون الملف بصيغة JSON')
        return redirect('backups:backup_dashboard')

    _ensure_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'imported_{timestamp}.json'
    filepath = os.path.join(BACKUP_DIR, filename)

    with open(filepath, 'wb') as f:
        for chunk in uploaded.chunks():
            f.write(chunk)

    try:
        result = subprocess.run(
            [settings.BASE_DIR / 'manage.py', 'loaddata', filepath],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise Exception(f'loaddata failed: {result.stderr}')

        messages.success(request, 'تم استيراد البيانات بنجاح')
        os.remove(filepath)
    except Exception as e:
        messages.error(request, 'فشلت العملية. يرجى المحاولة لاحقاً.')
        logger.exception('Backup operation failed')

    return redirect('backups:backup_dashboard')


@login_required
def backup_settings_view(request):
    backup_settings = BackupSettings.get_settings()

    if request.method == 'POST':
        form = BackupSettingsForm(request.POST, instance=backup_settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم حفظ إعدادات النسخ الاحتياطي بنجاح')
            return redirect('backups:backup_settings')
    else:
        form = BackupSettingsForm(instance=backup_settings)

    return render(request, 'backups/backup_settings.html', {'form': form, 'backup_settings': backup_settings})


# ============================================================================
# استعادة ضبط المصنع — نظام اعتماد مزدوج (طبقة العرض فقط؛ المنطق في factory_reset.py)
# ============================================================================
SCREEN = 'system.factory_reset'


@screen_permission_required(SCREEN, 'view')
def factory_reset_home(request):
    requests_qs = FactoryResetRequest.objects.select_related(
        'requested_by', 'reviewed_by', 'executed_by')[:100]
    active = FactoryResetRequest.objects.filter(
        status__in=FactoryResetRequest.ACTIVE_STATUSES
    ).select_related('requested_by', 'reviewed_by').first()
    context = {
        'reset_requests': requests_qs,
        'active_request': active,
        'confirm_phrase': fr.CONFIRM_PHRASE,
        'approval_window': fr.APPROVAL_WINDOW_MINUTES,
        'scope_choices': FactoryResetRequest.SCOPE_CHOICES,
    }
    return render(request, 'backups/factory_reset.html', context)


@require_POST
@screen_permission_required(SCREEN, 'add')
def factory_reset_request(request):
    try:
        fr.create_request(
            request.user,
            request.POST.get('reason', ''),
            request.POST.get('reset_scope', FactoryResetRequest.SCOPE_BUSINESS),
            fr.meta_from_request(request),
        )
        messages.success(request, 'تم تقديم طلب الاستعادة. بانتظار اعتماد جهة مخوّلة.')
    except fr.FactoryResetError as e:
        messages.error(request, str(e))
    return redirect('backups:factory_reset_home')


@require_POST
@screen_permission_required(SCREEN, 'edit')
def factory_reset_approve(request, pk):
    try:
        _req, token = fr.approve_request(pk, request.user, fr.meta_from_request(request))
        messages.success(
            request,
            f'تم الاعتماد. رمز التنفيذ (يُسلَّم للمنفّذ ولمرة واحدة فقط): {token}')
    except FactoryResetRequest.DoesNotExist:
        messages.error(request, 'الطلب غير موجود.')
    except fr.FactoryResetError as e:
        messages.error(request, str(e))
    return redirect('backups:factory_reset_home')


@require_POST
@screen_permission_required(SCREEN, 'edit')
def factory_reset_reject(request, pk):
    try:
        fr.reject_request(pk, request.user, request.POST.get('notes', ''),
                          fr.meta_from_request(request))
        messages.success(request, 'تم رفض الطلب.')
    except FactoryResetRequest.DoesNotExist:
        messages.error(request, 'الطلب غير موجود.')
    except fr.FactoryResetError as e:
        messages.error(request, str(e))
    return redirect('backups:factory_reset_home')


@require_POST
@screen_permission_required(SCREEN, 'add')
def factory_reset_cancel(request, pk):
    try:
        req = FactoryResetRequest.objects.get(pk=pk)
        # الطالب يلغي طلبه، أو صاحب مستوى التعديل
        perms = None
        if not request.user.is_superuser and req.requested_by_id != request.user.id:
            from access_control.resolver import resolve
            perms = resolve(request.user)
            if not perms.can(SCREEN, 'edit'):
                messages.error(request, 'لا تملك صلاحية إلغاء هذا الطلب.')
                return redirect('backups:factory_reset_home')
        fr.cancel_request(pk, request.user)
        messages.success(request, 'تم إلغاء الطلب.')
    except FactoryResetRequest.DoesNotExist:
        messages.error(request, 'الطلب غير موجود.')
    except fr.FactoryResetError as e:
        messages.error(request, str(e))
    return redirect('backups:factory_reset_home')


@require_POST
@screen_permission_required(SCREEN, 'delete')
def factory_reset_execute(request, pk):
    try:
        _req, deleted = fr.execute_request(
            pk, request.user,
            token=request.POST.get('token', ''),
            phrase=request.POST.get('phrase', ''),
            password=request.POST.get('password', ''),
            request_meta=fr.meta_from_request(request),
        )
        messages.success(
            request,
            'تم تنفيذ استعادة ضبط المصنع بنجاح. أُنشئت نسخة أمان قبل المسح. '
            'يُنصح بإعادة تشغيل الخادم.')
    except FactoryResetRequest.DoesNotExist:
        messages.error(request, 'الطلب غير موجود.')
    except fr.FactoryResetError as e:
        messages.error(request, str(e))
    return redirect('backups:factory_reset_home')
