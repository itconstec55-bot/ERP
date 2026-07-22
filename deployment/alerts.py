"""
Alerts: Notification system for errors, health failures, updates, etc.
"""

import json
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'accounting_system.settings')

from deployment.config.settings import (
    ALERTS_EMAIL_FROM,
    ALERTS_EMAIL_PASS,
    ALERTS_EMAIL_PORT,
    ALERTS_EMAIL_SMTP,
    ALERTS_EMAIL_TO,
    ALERTS_EMAIL_USER,
    ALERTS_ENABLED,
    ALERTS_LOG_DIR,
    ALERTS_METHOD,
)

logger = logging.getLogger('alerts')

ALERTS_LOG = Path(ALERTS_LOG_DIR) / 'alerts.json'


class AlertLevel:
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class AlertManager:
    """Central alert manager."""

    def __init__(self):
        self.alerts = []
        self._load()

    def _load(self):
        if ALERTS_LOG.exists():
            try:
                self.alerts = json.loads(ALERTS_LOG.read_text(encoding='utf-8'))
            except Exception:
                self.alerts = []

    def _save(self):
        ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        ALERTS_LOG.write_text(json.dumps(self.alerts[-500:], indent=2, default=str), encoding='utf-8')

    def send(self, title, message, level=AlertLevel.INFO):
        if not ALERTS_ENABLED:
            return

        alert = {'timestamp': datetime.now().isoformat(), 'level': level, 'title': title, 'message': message}
        self.alerts.append(alert)
        self._save()

        log_fn = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.ERROR: logger.error,
            AlertLevel.CRITICAL: logger.critical,
        }.get(level, logger.info)
        log_fn(f'[{level.upper()}] {title}: {message}')

        if ALERTS_METHOD in ('email', 'both'):
            self._send_email(title, message, level)
        if ALERTS_METHOD in ('log', 'both'):
            self._write_log_file(alert)

    def _send_email(self, title, message, level):
        if not all([ALERTS_EMAIL_SMTP, ALERTS_EMAIL_TO, ALERTS_EMAIL_USER]):
            logger.warning('Email not configured, skipping alert email')
            return
        try:
            msg = MIMEMultipart()
            msg['From'] = ALERTS_EMAIL_FROM
            msg['To'] = ALERTS_EMAIL_TO
            msg['Subject'] = f'[Accounting System - {level.upper()}] {title}'
            body = f"""
النظام المحاسبي - تنبيه
━━━━━━━━━━━━━━━━━━━━━━━

المستوى: {level.upper()}
التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

العنوان: {title}
التفاصيل: {message}

━━━━━━━━━━━━━━━━━━━━━━━
自动警报 - نظام التوريدات المحاسبي
"""
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            with smtplib.SMTP(ALERTS_EMAIL_SMTP, ALERTS_EMAIL_PORT) as server:
                server.starttls()
                server.login(ALERTS_EMAIL_USER, ALERTS_EMAIL_PASS)
                server.sendmail(ALERTS_EMAIL_FROM, ALERTS_EMAIL_TO, msg.as_string())
            logger.info(f'Alert email sent: {title}')
        except Exception as e:
            logger.error(f'Failed to send email alert: {e}')

    def _write_log_file(self, alert):
        alert_file = Path(ALERTS_LOG_DIR) / 'alerts.log'
        alert_file.parent.mkdir(parents=True, exist_ok=True)
        with open(alert_file, 'a', encoding='utf-8') as f:
            f.write(f'[{alert["timestamp"]}] [{alert["level"].upper()}] {alert["title"]}: {alert["message"]}\n')

    def get_recent(self, count=50, level=None):
        alerts = self.alerts
        if level:
            alerts = [a for a in alerts if a['level'] == level]
        return alerts[-count:]


def alert_server_down(host, port):
    AlertManager().send('السيرفر متوقف', f'السيرفر على {host}:{port} لا يستجيب للطلبات', AlertLevel.CRITICAL)


def alert_server_restarted(attempts):
    AlertManager().send(
        'إعادة تشغيل السيرفر', f'تم إعادة تشغيل السيرفر تلقائياً (محاولة رقم {attempts})', AlertLevel.WARNING
    )


def alert_health_check_failed(failures, threshold):
    AlertManager().send(
        'فحص الحالة فشل', f'فشل فحص الحالة ({failures}/{threshold}) - سيتم إعادة التشغيل قريباً', AlertLevel.WARNING
    )


def alert_update_available(info):
    AlertManager().send('تحديث متاح', f'تم اكتشاف تحديث جديد: {json.dumps(info, default=str)[:200]}', AlertLevel.INFO)


def alert_update_applied(version=None):
    AlertManager().send(
        'تم تطبيق التحديث', f'تم تطبيق التحديث{" (" + version + ")" if version else ""} بنجاح', AlertLevel.INFO
    )


def alert_backup_complete(success, details=''):
    level = AlertLevel.INFO if success else AlertLevel.ERROR
    AlertManager().send(
        'النسخ الاحتياطي' if success else 'فشل النسخ الاحتياطي',
        f'اكتمل النسخ الاحتياطي {"بنجاح" if success else "بفشل"} {details}',
        level,
    )


def alert_disk_low(space_mb):
    AlertManager().send('مساحة القرص منخفضة', f'المساحة المتاحة على القرص: {space_mb}MB فقط', AlertLevel.WARNING)


def alert_database_error(error):
    AlertManager().send('خطأ في قاعدة البيانات', str(error)[:500], AlertLevel.CRITICAL)
