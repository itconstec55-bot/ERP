"""طبقة منطق استعادة ضبط المصنع (Maker-Checker).

مبدأ التصميم: عملية الحذف الفعلية لا توجد إلا في `execute_request`، وهي
تُعيد التحقق من *كل* الشروط بنفسها (دفاع في العمق) بصرف النظر عن الواجهة،
فلا يقع أي مسح ما لم تُستوفَ شروط الاعتماد المحددة مسبقاً.
"""
import hashlib
import logging
import os
import secrets
import zipfile
from datetime import datetime, timedelta

from django.apps import apps as django_apps
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from audit.models import log_action
from .models import Backup, FactoryResetRequest

logger = logging.getLogger('accounting')

# مهلة صلاحية الاعتماد قبل التنفيذ (بالدقائق)
APPROVAL_WINDOW_MINUTES = 30
# العبارة التي يجب على المنفّذ كتابتها حرفياً وقت التنفيذ
CONFIRM_PHRASE = 'احذف جميع البيانات نهائيا'

# التطبيقات التي لا تُمسّ إطلاقاً (نظام + مساءلة + دخول)
_SYSTEM_APPS = {'admin', 'auth', 'contenttypes', 'sessions', 'sites'}
_ACCOUNTABILITY_APPS = {'audit', 'backups', 'access_control'}
_LOGIN_APPS = {'users'}
_CONFIG_APPS = {'company', 'currency'}

PRESERVE_BUSINESS = _SYSTEM_APPS | _ACCOUNTABILITY_APPS | _LOGIN_APPS | _CONFIG_APPS
PRESERVE_FULL = _SYSTEM_APPS | _ACCOUNTABILITY_APPS | _LOGIN_APPS

BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups_storage')


class FactoryResetError(Exception):
    """خطأ منطقي في سير عمل الاستعادة (يُعرض للمستخدم بأمان)."""


# ----------------------------------------------------------------------------
# أدوات مساعدة
# ----------------------------------------------------------------------------
def meta_from_request(request):
    return {
        'ip': request.META.get('REMOTE_ADDR'),
        'ua': request.META.get('HTTP_USER_AGENT', '')[:500],
    }


def _hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _audit(user, action, req, note='', request_meta=None):
    changes = {
        'reset_scope': req.reset_scope,
        'status': req.status,
        'note': note,
    }
    log_action(user, action, 'backups.FactoryResetRequest',
               object_id=req.id, object_repr=str(req), changes=changes)


def _preserve_set(scope):
    return PRESERVE_FULL if scope == FactoryResetRequest.SCOPE_FULL else PRESERVE_BUSINESS


# ----------------------------------------------------------------------------
# 1) الطلب (Maker)
# ----------------------------------------------------------------------------
@transaction.atomic
def create_request(user, reason, scope, request_meta):
    reason = (reason or '').strip()
    if len(reason) < 10:
        raise FactoryResetError('يجب إدخال مبرر واضح لا يقل عن 10 أحرف.')
    if scope not in dict(FactoryResetRequest.SCOPE_CHOICES):
        raise FactoryResetError('نطاق استعادة غير صالح.')
    if FactoryResetRequest.objects.filter(status__in=FactoryResetRequest.ACTIVE_STATUSES).exists():
        raise FactoryResetError('يوجد طلب استعادة نشط بالفعل. يجب إغلاقه قبل إنشاء طلب جديد.')

    req = FactoryResetRequest.objects.create(
        reason=reason,
        reset_scope=scope,
        status=FactoryResetRequest.STATUS_PENDING,
        requested_by=user,
        requester_ip=request_meta.get('ip'),
        requester_user_agent=request_meta.get('ua', ''),
    )
    _audit(user, 'create', req, note='تقديم طلب استعادة')
    return req


# ----------------------------------------------------------------------------
# 2) الاعتماد / الرفض (Checker)
# ----------------------------------------------------------------------------
@transaction.atomic
def approve_request(req_id, approver, request_meta):
    req = FactoryResetRequest.objects.select_for_update().get(pk=req_id)
    if req.status != FactoryResetRequest.STATUS_PENDING:
        raise FactoryResetError('لا يمكن اعتماد هذا الطلب في حالته الحالية.')
    # فصل المهام: الطالب لا يعتمد طلبه
    if req.requested_by_id == approver.id:
        raise FactoryResetError('لا يجوز للطالب اعتماد طلبه بنفسه (فصل المهام).')

    token = secrets.token_urlsafe(24)
    req.status = FactoryResetRequest.STATUS_APPROVED
    req.reviewed_by = approver
    req.reviewed_at = timezone.now()
    req.review_ip = request_meta.get('ip')
    req.review_user_agent = request_meta.get('ua', '')
    req.approval_expires_at = timezone.now() + timedelta(minutes=APPROVAL_WINDOW_MINUTES)
    req.execution_token_hash = _hash_token(token)
    req.save()
    _audit(approver, 'permission_change', req, note='اعتماد الطلب وإصدار رمز تنفيذ')
    # يُعاد الرمز الصريح مرة واحدة فقط ليُسلَّم للمنفّذ (لا يُخزَّن صريحاً)
    return req, token


@transaction.atomic
def reject_request(req_id, approver, notes, request_meta):
    req = FactoryResetRequest.objects.select_for_update().get(pk=req_id)
    if req.status != FactoryResetRequest.STATUS_PENDING:
        raise FactoryResetError('لا يمكن رفض هذا الطلب في حالته الحالية.')
    req.status = FactoryResetRequest.STATUS_REJECTED
    req.reviewed_by = approver
    req.reviewed_at = timezone.now()
    req.review_ip = request_meta.get('ip')
    req.review_user_agent = request_meta.get('ua', '')
    req.review_notes = (notes or '').strip()
    req.execution_token_hash = ''
    req.save()
    _audit(approver, 'permission_change', req, note='رفض الطلب')
    return req


@transaction.atomic
def cancel_request(req_id, user):
    req = FactoryResetRequest.objects.select_for_update().get(pk=req_id)
    if req.status not in (FactoryResetRequest.STATUS_PENDING, FactoryResetRequest.STATUS_APPROVED):
        raise FactoryResetError('لا يمكن إلغاء هذا الطلب في حالته الحالية.')
    req.status = FactoryResetRequest.STATUS_CANCELLED
    req.execution_token_hash = ''
    req.save()
    _audit(user, 'update', req, note='إلغاء الطلب')
    return req


# ----------------------------------------------------------------------------
# 3) التنفيذ (Executor) — الطبقة الوحيدة التي تُنفّذ الحذف
# ----------------------------------------------------------------------------
def _create_safety_backup(user):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'pre_reset_full_{stamp}.zip'
    filepath = os.path.join(BACKUP_DIR, filename)
    backup = Backup.objects.create(
        name=f'نسخة أمان قبل الاستعادة {stamp}',
        backup_type='full', file_path='', status='pending', created_by=user,
    )
    try:
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            db_path = str(settings.DATABASES['default']['NAME'])
            zf.write(db_path, 'db.sqlite3')
            for suffix in ('-wal', '-shm'):
                if os.path.exists(db_path + suffix):
                    zf.write(db_path + suffix, 'db.sqlite3' + suffix)
            if os.path.exists(settings.MEDIA_ROOT):
                for root, _dirs, files in os.walk(settings.MEDIA_ROOT):
                    for f in files:
                        fp = os.path.join(root, f)
                        arc = os.path.relpath(fp, settings.MEDIA_ROOT)
                        zf.write(fp, os.path.join('media', arc))
        backup.file_path = filepath
        backup.file_size = os.path.getsize(filepath)
        backup.status = 'completed'
        backup.save()
        return backup
    except Exception:
        backup.status = 'failed'
        backup.save()
        logger.exception('Safety backup before factory reset failed')
        raise FactoryResetError('تعذّر إنشاء نسخة الأمان قبل الاستعادة؛ أُلغيت العملية حفاظاً على البيانات.')


def _wipe_data(scope):
    """يمسح بيانات التطبيقات غير المحميّة داخل معاملة واحدة.

    يُستخدم _raw_delete مع تعطيل قيود المفاتيح الأجنبية لتفادي أخطاء الترتيب
    وضمان مسح متّسق. الجداول المحميّة (النظام/الدخول/المساءلة) لا تُمسّ.
    """
    preserve = _preserve_set(scope)
    models = [
        m for m in django_apps.get_models()
        if m._meta.managed and m._meta.app_label not in preserve
    ]
    deleted = {}
    with transaction.atomic():
        with connection.constraint_checks_disabled():
            for model in models:
                qs = model._base_manager.all()
                count = qs.count()
                if count:
                    qs._raw_delete(qs.db)
                    deleted[model._meta.label] = count
    return deleted


def execute_request(req_id, executor, token, phrase, password, request_meta):
    """ينفّذ الاستعادة بعد إعادة التحقق الكامل. آمن ضد التنفيذ المزدوج.

    ملاحظة تصميمية: نجمع نتيجة الفحص داخل قفل الصف ثم *نُخرِج* التسجيل والرفض
    خارج المعاملة، حتى لا يُلغى أثر التدقيق أو تغيّر الحالة عند رفع الاستثناء.
    """
    error = None          # رسالة تُرفع للمستخدم
    denied_note = None    # يُسجَّل كمحاولة رفض في سجل التدقيق
    proceed = False

    # قفل الصف لمنع التنفيذ المتزامن/المزدوج، والفحص الذرّي
    with transaction.atomic():
        req = FactoryResetRequest.objects.select_for_update().get(pk=req_id)

        if not executor.is_superuser:                                   # (أ)
            error, denied_note = 'التنفيذ مقصور على مدير النظام (superuser).', 'تنفيذ بلا superuser'
        elif req.status != FactoryResetRequest.STATUS_APPROVED:         # (ب)
            error = 'الطلب غير معتمد أو نُفّذ مسبقاً.'
        elif req.is_expired():                                          # (ج)
            req.status = FactoryResetRequest.STATUS_EXPIRED
            req.execution_token_hash = ''
            req.save(update_fields=['status', 'execution_token_hash'])
            error = 'انتهت صلاحية الاعتماد؛ يلزم اعتماد جديد.'
        elif req.reviewed_by_id == executor.id:                        # (د)
            error, denied_note = 'لا يجوز لمن اعتمد الطلب أن ينفّذه بنفسه (فصل المهام).', 'المعتمِد يحاول التنفيذ'
        elif not req.execution_token_hash or _hash_token(token or '') != req.execution_token_hash:  # (هـ)
            error, denied_note = 'رمز التنفيذ غير صحيح.', 'رمز تنفيذ غير صحيح'
        elif (phrase or '').strip() != CONFIRM_PHRASE:                 # (و)
            error = 'عبارة التأكيد غير مطابقة.'
        elif not password or not executor.check_password(password):    # (ز)
            error, denied_note = 'كلمة المرور غير صحيحة.', 'فشل إعادة المصادقة'
        else:
            # اجتياز كل الشروط: ننتقل لحالة التنفيذ ونستهلك الرمز
            req.status = FactoryResetRequest.STATUS_EXECUTING
            req.executed_by = executor
            req.executed_at = timezone.now()
            req.execution_ip = request_meta.get('ip')
            req.execution_user_agent = request_meta.get('ua', '')
            req.execution_token_hash = ''  # استهلاك لمرة واحدة
            req.save()
            proceed = True

    # خارج المعاملة: التسجيل والرفض (يبقى الأثر محفوظاً)
    if denied_note:
        _audit(executor, 'access_denied', req, note=denied_note)
    if not proceed:
        raise FactoryResetError(error)

    _audit(executor, 'permission_change', req, note='بدء التنفيذ بعد اجتياز كل الضوابط')

    # نسخة الأمان الإلزامية (خارج قفل الصف، تُلغى العملية إن فشلت)
    try:
        backup = _create_safety_backup(executor)
    except FactoryResetError:
        req.status = FactoryResetRequest.STATUS_APPROVED  # يمكن إعادة المحاولة
        req.save(update_fields=['status'])
        raise

    # الحذف الفعلي
    try:
        deleted = _wipe_data(req.reset_scope)
        req.safety_backup = backup
        req.status = FactoryResetRequest.STATUS_COMPLETED
        req.result_notes = 'تم المسح. الجداول المتأثرة: ' + ', '.join(
            f'{k}={v}' for k, v in deleted.items()) or 'لا توجد بيانات للمسح.'
        req.save()
        _audit(executor, 'delete', req, note=f'اكتمال الاستعادة ({req.reset_scope})')
        log_action(executor, 'backup', 'backups.Backup', object_id=backup.id,
                   object_repr=backup.name, changes={'context': 'pre_factory_reset'})
        return req, deleted
    except Exception as e:
        req.status = FactoryResetRequest.STATUS_FAILED
        req.result_notes = f'فشل التنفيذ: {e}'
        req.save()
        _audit(executor, 'update', req, note='فشل التنفيذ — تتوفر نسخة الأمان للاسترجاع')
        logger.exception('Factory reset execution failed')
        raise FactoryResetError('فشل تنفيذ الاستعادة. تتوفر نسخة أمان للاسترجاع.')
