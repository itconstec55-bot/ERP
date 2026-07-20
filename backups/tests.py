from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from audit.models import AuditLog
from budget.models import CostCenter
from . import factory_reset as fr
from .models import Backup, FactoryResetRequest

User = get_user_model()
META = {'ip': '127.0.0.1', 'ua': 'pytest'}


class FactoryResetWorkflowTests(TestCase):
    def setUp(self):
        self.maker = User.objects.create_user('maker', password='pw-maker-123')
        self.checker = User.objects.create_user('checker', password='pw-check-123')
        self.executor = User.objects.create_superuser('root', password='pw-root-123')

    def _new_request(self):
        return fr.create_request(self.maker, 'مبرر اختبار كافٍ للطول', 'business_data', META)

    # --- separation of duties -------------------------------------------
    def test_requester_cannot_approve_own_request(self):
        req = self._new_request()
        with self.assertRaises(fr.FactoryResetError):
            fr.approve_request(req.id, self.maker, META)

    def test_approver_cannot_execute_own_approval(self):
        req = self._new_request()
        _r, token = fr.approve_request(req.id, self.checker, META)
        # المعتمِد (checker) لو كان superuser لا يجوز أن ينفّذ
        self.checker.is_superuser = True
        self.checker.save()
        with self.assertRaises(fr.FactoryResetError):
            fr.execute_request(req.id, self.checker, token, fr.CONFIRM_PHRASE,
                               'pw-check-123', META)

    def test_only_one_active_request(self):
        self._new_request()
        with self.assertRaises(fr.FactoryResetError):
            self._new_request()

    # --- execution guards ------------------------------------------------
    def test_non_superuser_cannot_execute(self):
        req = self._new_request()
        _r, token = fr.approve_request(req.id, self.checker, META)
        with self.assertRaises(fr.FactoryResetError):
            fr.execute_request(req.id, self.maker, token, fr.CONFIRM_PHRASE,
                               'pw-maker-123', META)

    def test_wrong_token_rejected(self):
        req = self._new_request()
        fr.approve_request(req.id, self.checker, META)
        with self.assertRaises(fr.FactoryResetError):
            fr.execute_request(req.id, self.executor, 'BAD', fr.CONFIRM_PHRASE,
                               'pw-root-123', META)

    def test_wrong_phrase_rejected(self):
        req = self._new_request()
        _r, token = fr.approve_request(req.id, self.checker, META)
        with self.assertRaises(fr.FactoryResetError):
            fr.execute_request(req.id, self.executor, token, 'خطأ', 'pw-root-123', META)

    def test_wrong_password_rejected(self):
        req = self._new_request()
        _r, token = fr.approve_request(req.id, self.checker, META)
        with self.assertRaises(fr.FactoryResetError):
            fr.execute_request(req.id, self.executor, token, fr.CONFIRM_PHRASE,
                               'wrong', META)

    def test_expired_approval_rejected(self):
        req = self._new_request()
        _r, token = fr.approve_request(req.id, self.checker, META)
        req.refresh_from_db()
        req.approval_expires_at = timezone.now() - timedelta(minutes=1)
        req.save()
        with self.assertRaises(fr.FactoryResetError):
            fr.execute_request(req.id, self.executor, token, fr.CONFIRM_PHRASE,
                               'pw-root-123', META)
        req.refresh_from_db()
        self.assertEqual(req.status, FactoryResetRequest.STATUS_EXPIRED)

    # --- happy path + scope + accountability -----------------------------
    def test_full_workflow_wipes_business_preserves_system(self):
        CostCenter.objects.create(code='CC1', name='مركز تكلفة')
        self.assertEqual(CostCenter.objects.count(), 1)
        users_before = User.objects.count()

        req = self._new_request()
        _r, token = fr.approve_request(req.id, self.checker, META)
        # قاعدة بيانات الاختبار في الذاكرة لا يوجد لها ملف يُضغط؛ نستبدل نسخة الأمان
        fake_backup = Backup.objects.create(
            name='نسخة أمان اختبارية', backup_type='full',
            file_path='x', file_size=1, status='completed', created_by=self.executor)
        with mock.patch.object(fr, '_create_safety_backup', return_value=fake_backup):
            result_req, deleted = fr.execute_request(
                req.id, self.executor, token, fr.CONFIRM_PHRASE, 'pw-root-123', META)

        self.assertEqual(result_req.status, FactoryResetRequest.STATUS_COMPLETED)
        # بيانات المعاملات مُسحت
        self.assertEqual(CostCenter.objects.count(), 0)
        self.assertIn('budget.CostCenter', deleted)
        # المستخدمون محفوظون (طبقة الدخول)
        self.assertEqual(User.objects.count(), users_before)
        # سجل الطلب نفسه محفوظ (المساءلة)
        self.assertTrue(FactoryResetRequest.objects.filter(pk=req.id).exists())
        # نسخة الأمان أُنشئت وربطت
        self.assertIsNotNone(result_req.safety_backup)
        # هوية المنفّذ والوقت مسجّلان
        self.assertEqual(result_req.executed_by, self.executor)
        self.assertIsNotNone(result_req.executed_at)
        # أثر تدقيق للحذف موجود
        self.assertTrue(AuditLog.objects.filter(
            model_name='backups.FactoryResetRequest', action='delete').exists())

    def test_reject_blocks_execution(self):
        req = self._new_request()
        fr.reject_request(req.id, self.checker, 'غير مبرر', META)
        req.refresh_from_db()
        self.assertEqual(req.status, FactoryResetRequest.STATUS_REJECTED)
        self.assertEqual(req.execution_token_hash, '')
