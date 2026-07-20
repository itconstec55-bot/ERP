"""
خدمة التكامل مع منظومة الفاتورة الإلكترونية (ETA)
Egypt Tax Authority E-Invoicing API Service

التدفق:
1. الحصول على توكن الوصول عبر بيانات الاعتماد (client_id / client_secret)
2. توقيع المستند رقمياً (PKI) إن توفرت الشهادة
3. إرسال المستند عبر endpoints الخاصة بالإرسال
4. متابعة حالة المستند
"""
import json
import logging
from django.conf import settings
from django.utils import timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger('accounting')


class ETAAPIError(Exception):
    """خطأ في الاتصال بمنظومة الفاتورة الإلكترونية"""
    def __init__(self, message, status_code=None, response_body=None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class ETAService:
    """
    خدمة الوصول لـ API الخاص بمصلحة الضرائب المصرية
    """

    def __init__(self, connection):
        self.connection = connection
        self.base_url = connection.base_url
        self.token = None
        self.token_expires_at = None

    # ──────────────────────────────────────────────────────────
    # إدارة الجلسة (Session) مع إعادة المحاولة
    # ──────────────────────────────────────────────────────────
    def _get_session(self):
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=['GET', 'POST']
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        return session

    # ──────────────────────────────────────────────────────────
    # المصادقة (Authentication)
    # ──────────────────────────────────────────────────────────
    def authenticate(self):
        """
        الحصول على توكن الوصول من مصلحة الضرائب
        POST /api/v1/auth/token
        """
        if self.token and self.token_expires_at and self.token_expires_at > timezone.now():
            return self.token

        url = f'{self.base_url}/v1/auth/token'
        payload = {
            'grantType': 'client_credentials',
            'clientId': self.connection.client_id or '',
            'clientSecret': self.connection.client_secret or '',
        }
        try:
            session = self._get_session()
            resp = session.post(url, json=payload, timeout=30)
        except requests.RequestException as e:
            raise ETAAPIError(f'فشل الاتصال بمنظومة الضرائب: {e}')

        if resp.status_code != 200:
            raise ETAAPIError(
                f'فشل المصادقة مع مصلحة الضرائب (كود {resp.status_code})',
                status_code=resp.status_code,
                response_body=resp.text[:1000]
            )

        data = resp.json()
        self.token = data.get('access_token') or data.get('id_token')
        expires_in = int(data.get('expires_in', 3600))
        self.token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in - 60)
        return self.token

    # ──────────────────────────────────────────────────────────
    # إرسال المستندات (Document Submission)
    # ──────────────────────────────────────────────────────────
    def submit_documents(self, documents):
        """
        إرسال مستند أو أكثر لمصلحة الضرائب
        المستندات يجب أن تكون قائمة من dicts (صيغة ETA)
        POST /api/v1/document-submissions

        يُرجع: قائمة من dicts تحتوي على uuid و submission_uuid لكل مستند
        """
        token = self.authenticate()
        url = f'{self.base_url}/v1/document-submissions'

        payload = [documents] if isinstance(documents, dict) else list(documents)

        session = self._get_session()
        session.headers.update({'Authorization': f'Bearer {token}'})

        try:
            resp = session.post(url, json=payload, timeout=60)
        except requests.RequestException as e:
            raise ETAAPIError(f'فشل إرسال المستندات: {e}')

        if resp.status_code not in (200, 202, 207):
            raise ETAAPIError(
                f'فشل إرسال المستندات (كود {resp.status_code})',
                status_code=resp.status_code,
                response_body=resp.text[:2000]
            )

        return resp.json()

    # ──────────────────────────────────────────────────────────
    # متابعة حالة المستند (Status Tracking)
    # ──────────────────────────────────────────────────────────
    def get_document_status(self, submission_uuid):
        """
        متابعة حالة المستند المرسل
        GET /api/v1/document-submissions/{submission_uuid}/status
        """
        token = self.authenticate()
        url = f'{self.base_url}/v1/document-submissions/{submission_uuid}/status'

        session = self._get_session()
        session.headers.update({'Authorization': f'Bearer {token}'})

        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as e:
            raise ETAAPIError(f'فشل متابعة حالة المستند: {e}')

        if resp.status_code != 200:
            raise ETAAPIError(
                f'فشل متابعة الحالة (كود {resp.status_code})',
                status_code=resp.status_code,
                response_body=resp.text[:1000]
            )

        return resp.json()

    def get_document_details(self, uuid):
        """
        جلب تفاصيل المستند (بما فيها الرقم الطويل وQR)
        GET /api/v1/documents/{uuid}/raw
        """
        token = self.authenticate()
        url = f'{self.base_url}/v1/documents/{uuid}/raw'

        session = self._get_session()
        session.headers.update({'Authorization': f'Bearer {token}'})

        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as e:
            raise ETAAPIError(f'فشل جلب تفاصيل المستند: {e}')

        if resp.status_code != 200:
            raise ETAAPIError(
                f'فشل جلب التفاصيل (كود {resp.status_code})',
                status_code=resp.status_code,
                response_body=resp.text[:1000]
            )

        return resp.json()

    def void_document(self, document_uuid, reason=''):
        """
        إلغاء مستند ضريبي (Void/Reject)
        PUT /api/v1/documents/{uuid}/state
        """
        token = self.authenticate()
        url = f'{self.base_url}/v1/documents/{document_uuid}/state'
        payload = {'status': 'rejected', 'reason': reason or 'تم الإلغاء يدوياً'}

        session = self._get_session()
        session.headers.update({'Authorization': f'Bearer {token}'})

        try:
            resp = session.put(url, json=payload, timeout=30)
        except requests.RequestException as e:
            raise ETAAPIError(f'فشل إلغاء المستند: {e}')

        if resp.status_code not in (200, 202, 204):
            raise ETAAPIError(
                f'فشل إلغاء المستند (كود {resp.status_code})',
                status_code=resp.status_code,
                response_body=resp.text[:1000]
            )

        return resp.json() if resp.text else {'status': 'rejected'}
