"""
اختبارات شاملة لنظام المراقبة (Monitoring)
تشمل: المقاييس النظامية، السجلات، لوحة المراقبة، نقاط الوصول API

التقنيات المستخدمة:
- patch على psutil مباشرة (لأن الاستيراد يحدث داخل الدوال)
- mock __import__ لمحاكاة عدم توفر psutil
- ملفات مؤقتة لعمليات الإدخال/الإخراج
"""

import builtins
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import Client

from deployment.monitoring import (
    BASE_DIR,
    MAX_HISTORY,
    get_all_metrics,
    get_cpu_percent,
    get_db_size,
    get_disk_info,
    get_memory_info,
    get_metrics_history,
    get_network_info,
    get_process_info,
    get_service_status,
    get_uptime,
    save_metrics_history,
)

ORIGINAL_IMPORT = builtins.__import__


def _import_blocker(name, *args, **kwargs):
    """拦截 الاستيراد لمنع psutil فقط"""
    if name == 'psutil':
        raise ImportError("No module named 'psutil'")
    return ORIGINAL_IMPORT(name, *args, **kwargs)


# ============================================================
# اختبارات get_cpu_percent()
# ============================================================


class TestGetCpuPercent:
    """اختبار دالة الحصول على نسبة استخدام المعالج"""

    def test_psutil_returns_float(self):
        """اختبار إرجاع float عند توفر psutil"""
        with patch('psutil.cpu_percent', return_value=42.5) as mock_cpu:
            result = get_cpu_percent()
            assert result == 42.5
            mock_cpu.assert_called_once_with(interval=0.5)

    def test_psutil_returns_zero(self):
        """اختبار إرجاع صفر عند عدم استخدام المعالج"""
        with patch('psutil.cpu_percent', return_value=0.0):
            result = get_cpu_percent()
            assert result == 0.0

    def test_psutil_returns_high_value(self):
        """اختبار إرجاع نسبة مرتفعة عند ازدحام المعالج"""
        with patch('psutil.cpu_percent', return_value=99.9):
            result = get_cpu_percent()
            assert result == 99.9

    def test_windows_wmic_fallback(self):
        """اختبار المسار البديل عبر wmic على ويندوز"""
        mock_result = MagicMock()
        mock_result.stdout = 'LoadPercentage\n25\n'
        with patch('builtins.__import__', side_effect=_import_blocker):
            with patch('deployment.monitoring.sys.platform', 'win32'):
                with patch('deployment.monitoring.subprocess.run', return_value=mock_result):
                    result = get_cpu_percent()
                    assert result == 25.0

    def test_windows_wmic_non_numeric_skipped(self):
        """اختبار تخطي القيم غير الرقمية في خرج wmic"""
        mock_result = MagicMock()
        mock_result.stdout = 'LoadPercentage\nN/A\n\n'
        with patch('builtins.__import__', side_effect=_import_blocker):
            with patch('deployment.monitoring.sys.platform', 'win32'):
                with patch('deployment.monitoring.subprocess.run', return_value=mock_result):
                    result = get_cpu_percent()
                    assert result == 0.0

    def test_linux_top_fallback(self):
        """اختبار المسار البديل عبر top على لينكس"""
        mock_result = MagicMock()
        mock_result.stdout = '%Cpu(s): 10.5 us, 2.0 sy, 0.0 ni, 87.0 id, 0.5 wa\n'
        with patch('builtins.__import__', side_effect=_import_blocker):
            with patch('deployment.monitoring.sys.platform', 'linux'):
                with patch('deployment.monitoring.subprocess.run', return_value=mock_result):
                    result = get_cpu_percent()
                    assert abs(result - 13.0) < 0.1

    def test_all_fallbacks_fail_returns_zero(self):
        """اختبار إرجاع 0.0 عند فشل جميع الطرق البديلة"""
        with patch('builtins.__import__', side_effect=_import_blocker):
            with patch('deployment.monitoring.subprocess.run', side_effect=Exception('wmic failed')):
                result = get_cpu_percent()
                assert result == 0.0

    def test_subprocess_timeout_returns_zero(self):
        """اختبار التعامل مع انتهاء المهلة في subprocess"""
        with patch('builtins.__import__', side_effect=_import_blocker):
            with patch('deployment.monitoring.subprocess.run', side_effect=Exception('timeout')):
                result = get_cpu_percent()
                assert result == 0.0


# ============================================================
# اختبارات get_memory_info()
# ============================================================


class TestGetMemoryInfo:
    """اختبار دالة الحصول على معلومات الذاكرة"""

    def test_psutil_returns_correct_dict(self):
        """اختبار إرجاع قاموس صحيح مع psutil"""
        mock_mem = MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_mem.available = 4 * 1024 * 1024 * 1024
        mock_mem.used = 4 * 1024 * 1024 * 1024
        mock_mem.percent = 50.0

        mock_swap = MagicMock()
        mock_swap.total = 2 * 1024 * 1024 * 1024
        mock_swap.used = 512 * 1024 * 1024
        mock_swap.percent = 25.0

        with patch('psutil.virtual_memory', return_value=mock_mem):
            with patch('psutil.swap_memory', return_value=mock_swap):
                result = get_memory_info()

        assert result['total_mb'] == 8192
        assert result['available_mb'] == 4096
        assert result['used_mb'] == 4096
        assert result['percent'] == 50.0
        assert result['swap_total_mb'] == 2048
        assert result['swap_used_mb'] == 512
        assert result['swap_percent'] == 25.0

    def test_swap_info_included(self):
        """اختبار تضمين معلومات الـ swap"""
        mock_mem = MagicMock()
        mock_mem.total = 4 * 1024 * 1024 * 1024
        mock_mem.available = 2 * 1024 * 1024 * 1024
        mock_mem.used = 2 * 1024 * 1024 * 1024
        mock_mem.percent = 50.0

        mock_swap = MagicMock()
        mock_swap.total = 1 * 1024 * 1024 * 1024
        mock_swap.used = 256 * 1024 * 1024
        mock_swap.percent = 25.0

        with patch('psutil.virtual_memory', return_value=mock_mem):
            with patch('psutil.swap_memory', return_value=mock_swap):
                result = get_memory_info()

        assert 'swap_total_mb' in result
        assert 'swap_used_mb' in result
        assert 'swap_percent' in result

    def test_wmic_fallback_on_windows(self):
        """اختبار المسار البديل عبر wmic على ويندوز"""
        mock_result = MagicMock()
        mock_result.stdout = (
            'TotalVisibleMemorySize  FreePhysicalMemory\n'
            '16384000                8192000\n'
        )
        with patch('builtins.__import__', side_effect=_import_blocker):
            with patch('deployment.monitoring.sys.platform', 'win32'):
                with patch('deployment.monitoring.subprocess.run', return_value=mock_result):
                    result = get_memory_info()

        assert result['total_mb'] > 0
        assert result['available_mb'] > 0

    def test_returns_zero_on_total_failure(self):
        """اختبار إرجاع قيم صفرية عند فشل كل شيء"""
        with patch('builtins.__import__', side_effect=_import_blocker):
            with patch('deployment.monitoring.subprocess.run', side_effect=Exception('failed')):
                result = get_memory_info()

        assert result['total_mb'] == 0
        assert result['available_mb'] == 0
        assert result['used_mb'] == 0
        assert result['percent'] == 0

    def test_wmic_invalid_output_returns_zero(self):
        """اختبار التعامل مع خرج wmic غير صالح"""
        mock_result = MagicMock()
        mock_result.stdout = 'garbage output\n'
        with patch('builtins.__import__', side_effect=_import_blocker):
            with patch('deployment.monitoring.sys.platform', 'win32'):
                with patch('deployment.monitoring.subprocess.run', return_value=mock_result):
                    result = get_memory_info()

        assert result['total_mb'] == 0

    def test_memory_values_are_integers(self):
        """اختبار أن قيم الذاكرة أعداد صحيحة"""
        mock_mem = MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_mem.available = 4 * 1024 * 1024 * 1024
        mock_mem.used = 4 * 1024 * 1024 * 1024
        mock_mem.percent = 50.0

        mock_swap = MagicMock()
        mock_swap.total = 2 * 1024 * 1024 * 1024
        mock_swap.used = 512 * 1024 * 1024
        mock_swap.percent = 25.0

        with patch('psutil.virtual_memory', return_value=mock_mem):
            with patch('psutil.swap_memory', return_value=mock_swap):
                result = get_memory_info()

        assert isinstance(result['total_mb'], int)
        assert isinstance(result['available_mb'], int)
        assert isinstance(result['used_mb'], int)


# ============================================================
# اختبارات get_disk_info()
# ============================================================


class TestGetDiskInfo:
    """اختبار دالة الحصول على معلومات القرص"""

    def test_returns_required_keys(self):
        """اختبار إرجاع جميع المفاتيح المطلوبة"""
        result = get_disk_info()
        for key in ['total_gb', 'used_gb', 'free_gb', 'percent']:
            assert key in result

    def test_calculation_consistency(self):
        """اختبار اتساق الحسابات بين المستخدم والمتاح والمجمل"""
        mock_usage = MagicMock()
        mock_usage.total = 100 * 1024**3
        mock_usage.used = 60 * 1024**3
        mock_usage.free = 40 * 1024**3

        with patch('deployment.monitoring.shutil.disk_usage', return_value=mock_usage):
            result = get_disk_info()

        assert result['total_gb'] == 100.0
        assert result['used_gb'] == 60.0
        assert result['free_gb'] == 40.0
        assert result['percent'] == 60.0

    def test_returns_zero_on_exception(self):
        """اختبار إرجاع صفر عند حدوث خطأ"""
        with patch('deployment.monitoring.shutil.disk_usage', side_effect=Exception('disk error')):
            result = get_disk_info()

        assert result['total_gb'] == 0
        assert result['used_gb'] == 0
        assert result['free_gb'] == 0
        assert result['percent'] == 0

    def test_free_plus_used_approximates_total(self):
        """اختبار أن free + used يقارب total"""
        mock_usage = MagicMock()
        mock_usage.total = 256 * 1024**3
        mock_usage.used = 128 * 1024**3
        mock_usage.free = 128 * 1024**3

        with patch('deployment.monitoring.shutil.disk_usage', return_value=mock_usage):
            result = get_disk_info()

        assert abs(result['used_gb'] + result['free_gb'] - result['total_gb']) < 0.2


# ============================================================
# اختبارات get_process_info()
# ============================================================


class TestGetProcessInfo:
    """اختبار دالة الحصول على معلومات العملية"""

    def test_returns_pid(self):
        """اختبار إرجاع رقم العملية الحالي"""
        result = get_process_info()
        assert result['pid'] == os.getpid()

    def test_psutil_returns_full_info(self):
        """اختبار إرجاع معلومات كاملة مع psutil"""
        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 5.5
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024
        mock_proc.num_threads.return_value = 12
        mock_proc.open_files.return_value = [1, 2, 3]
        mock_proc.connections.return_value = [1, 2]
        mock_proc.create_time.return_value = 1700000000.0

        with patch('psutil.Process', return_value=mock_proc):
            result = get_process_info()

        assert result['pid'] == os.getpid()
        assert result['cpu_percent'] == 5.5
        assert result['memory_mb'] == 100
        assert result['threads'] == 12
        assert result['open_files'] == 3
        assert result['connections'] == 2
        assert 'create_time' in result

    def test_import_error_returns_note(self):
        """اختبار إرجاع ملاحظة عند عدم توفر psutil"""
        with patch('builtins.__import__', side_effect=_import_blocker):
            result = get_process_info()

        assert result['pid'] == os.getpid()
        assert 'note' in result
        assert 'psutil' in result['note']

    def test_general_exception_returns_error(self):
        """اختبار إرجاع خطأ عند استثناء عام"""
        mock_proc = MagicMock()
        mock_proc.oneshot.return_value.__enter__ = MagicMock(side_effect=Exception('proc error'))
        mock_proc.oneshot.return_value.__exit__ = MagicMock(return_value=False)

        with patch('psutil.Process', return_value=mock_proc):
            result = get_process_info()

        assert 'error' in result
        assert 'proc error' in result['error']

    def test_create_time_is_iso_string(self):
        """اختبار أن وقت الإنشاء بتنسيق ISO"""
        result = get_process_info()
        if 'create_time' in result:
            datetime.fromisoformat(result['create_time'])


# ============================================================
# اختبارات get_uptime()
# ============================================================


class TestGetUptime:
    """اختبار دالة الحصول على مدة تشغيل النظام"""

    def test_linux_proc_uptime(self):
        """اختبار قراءة /proc/uptime على لينكس"""
        with patch('deployment.monitoring.sys.platform', 'linux'):
            mock_file = MagicMock()
            mock_file.return_value.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value='90061.37 180122.74'))
            )
            mock_file.return_value.__exit__ = MagicMock(return_value=False)
            with patch('builtins.open', mock_file):
                result = get_uptime()

        assert 'يوم' in result
        assert ':' in result

    def test_linux_uptime_format(self):
        """اختبار تنسيق النتيجة على لينكس"""
        with patch('deployment.monitoring.sys.platform', 'linux'):
            mock_file = MagicMock()
            mock_file.return_value.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value='86400.0 100000.0'))
            )
            mock_file.return_value.__exit__ = MagicMock(return_value=False)
            with patch('builtins.open', mock_file):
                result = get_uptime()

        assert 'يوم' in result
        assert '00:00' in result

    def test_windows_wmic_uptime(self):
        """اختبار قراءة wmic على ويندوز"""
        boot_time = datetime.now() - timedelta(days=2, hours=3, minutes=15)
        boot_str = boot_time.strftime('%Y%m%d%H%M%S') + '.000000+000'

        mock_result = MagicMock()
        mock_result.stdout = f'LastBootUpTime\n{boot_str}\n'

        with patch('deployment.monitoring.sys.platform', 'win32'):
            with patch('deployment.monitoring.subprocess.run', return_value=mock_result):
                result = get_uptime()

        assert 'يوم' in result
        assert ':' in result

    def test_returns_unavailable_on_error(self):
        """اختبار إرجاع 'غير متاح' عند الخطأ"""
        with patch('deployment.monitoring.sys.platform', 'linux'):
            with patch('builtins.open', side_effect=Exception('permission denied')):
                result = get_uptime()

        assert result == 'غير متاح'

    def test_unavailable_returned_when_wmic_invalid(self):
        """اختبار 'غير متاح' عند خرج wmic غير صالح"""
        mock_result = MagicMock()
        mock_result.stdout = 'garbage\n'

        with patch('deployment.monitoring.sys.platform', 'win32'):
            with patch('deployment.monitoring.subprocess.run', return_value=mock_result):
                result = get_uptime()

        assert result == 'غير متاح'


# ============================================================
# اختبارات get_network_info()
# ============================================================


class TestGetNetworkInfo:
    """اختبار دالة الحصول على معلومات الشبكة"""

    def test_returns_correct_dict(self):
        """اختبار إرجاع قاموس صحيح"""
        mock_net = MagicMock()
        mock_net.bytes_sent = 100 * 1024 * 1024
        mock_net.bytes_recv = 200 * 1024 * 1024
        mock_net.packets_sent = 5000
        mock_net.packets_recv = 8000

        with patch('psutil.net_io_counters', return_value=mock_net):
            result = get_network_info()

        assert result['bytes_sent_mb'] == 100.0
        assert result['bytes_recv_mb'] == 200.0
        assert result['packets_sent'] == 5000
        assert result['packets_recv'] == 8000

    def test_empty_dict_on_import_error(self):
        """اختبار إرجاع قاموس فارغ عند خطأ الاستيراد"""
        with patch('builtins.__import__', side_effect=_import_blocker):
            result = get_network_info()

        assert result == {}

    def test_empty_dict_on_runtime_error(self):
        """اختبار إرجاع قاموس فارغ عند خطأ تشغيلي"""
        with patch('psutil.net_io_counters', side_effect=RuntimeError('network error')):
            result = get_network_info()

        assert result == {}

    def test_zero_bytes_returns_zero_mb(self):
        """اختبار إرجاع صفر MB عند عدم وجود حركة بيانات"""
        mock_net = MagicMock()
        mock_net.bytes_sent = 0
        mock_net.bytes_recv = 0
        mock_net.packets_sent = 0
        mock_net.packets_recv = 0

        with patch('psutil.net_io_counters', return_value=mock_net):
            result = get_network_info()

        assert result['bytes_sent_mb'] == 0.0
        assert result['bytes_recv_mb'] == 0.0


# ============================================================
# اختبارات get_db_size()
# ============================================================


class TestGetDbSize:
    """اختبار دالة الحصول على حجم قاعدة البيانات"""

    def test_sqlite_detection(self):
        """اختبار اكتشاف SQLite"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'db.sqlite3'
            db_path.write_bytes(b'\x00' * (50 * 1024 * 1024))

            with patch('deployment.monitoring.BASE_DIR', Path(tmpdir)):
                result = get_db_size()

            assert result['engine'] == 'sqlite'
            assert result['size_mb'] == 50.0

    def test_returns_unknown_when_no_db(self):
        """اختبار إرجاع unknown عند عدم وجود ملف قاعدة بيانات"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('deployment.monitoring.BASE_DIR', Path(tmpdir)):
                result = get_db_size()

        assert result['engine'] == 'unknown'
        assert result['size_mb'] == 0

    def test_returns_engine_key(self):
        """اختبار وجود مفتاح engine في النتيجة"""
        result = get_db_size()
        assert 'engine' in result
        assert 'size_mb' in result
        assert result['engine'] in ['sqlite', 'postgresql', 'unknown']

    def test_small_sqlite_file(self):
        """اختبار قاعدة بيانات SQLite صغيرة"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'db.sqlite3'
            db_path.write_bytes(b'\x00' * 1024)

            with patch('deployment.monitoring.BASE_DIR', Path(tmpdir)):
                result = get_db_size()

            assert result['engine'] == 'sqlite'
            assert result['size_mb'] < 1.0


# ============================================================
# اختبارات get_all_metrics()
# ============================================================


class TestGetAllMetrics:
    """اختبار دالة جمع جميع المقاييس"""

    def test_returns_complete_dict(self):
        """اختبار إرجاع قاموس مقاييس كامل"""
        result = get_all_metrics()
        required_keys = [
            'timestamp', 'hostname', 'platform', 'python_version',
            'cpu', 'memory', 'disk', 'process', 'uptime', 'network', 'database',
        ]
        for key in required_keys:
            assert key in result, f'المفتاح {key} مفقود'

    def test_timestamp_is_valid_iso(self):
        """اختبار أن الطابع الزمني بصيغة ISO صالحة"""
        result = get_all_metrics()
        dt = datetime.fromisoformat(result['timestamp'])
        assert isinstance(dt, datetime)

    def test_cpu_section_structure(self):
        """اختبار هيكل قسم المعالج"""
        result = get_all_metrics()
        assert 'percent' in result['cpu']
        assert 'cores_physical' in result['cpu']
        assert 'cores_logical' in result['cpu']
        assert isinstance(result['cpu']['percent'], (int, float))

    def test_memory_section_is_dict(self):
        """اختبار أن قسم الذاكرة هو قاموس"""
        result = get_all_metrics()
        assert isinstance(result['memory'], dict)
        assert 'total_mb' in result['memory']

    def test_disk_section_is_dict(self):
        """اختبار أن قسم القرص هو قاموس"""
        result = get_all_metrics()
        assert isinstance(result['disk'], dict)
        assert 'total_gb' in result['disk']

    def test_process_section_has_pid(self):
        """اختبار أن قسم العملية يحتوي على PID"""
        result = get_all_metrics()
        assert 'pid' in result['process']
        assert result['process']['pid'] == os.getpid()

    def test_platform_info_populated(self):
        """اختبار ملء معلومات المنصة"""
        result = get_all_metrics()
        assert result['hostname']
        assert result['platform']
        assert result['python_version']

    def test_database_section_is_dict(self):
        """اختبار أن قسم قاعدة البيانات هو قاموس"""
        result = get_all_metrics()
        assert isinstance(result['database'], dict)
        assert 'engine' in result['database']
        assert 'size_mb' in result['database']

    def test_uptime_is_string(self):
        """اختبار أن مدة التشغيل نص"""
        result = get_all_metrics()
        assert isinstance(result['uptime'], str)


# ============================================================
# اختبارات save_metrics_history()
# ============================================================


class TestSaveMetricsHistory:
    """اختبار دالة حفظ سجل المقاييس"""

    def test_creates_new_file(self):
        """اختبار إنشاء ملف جديد"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            metrics = {
                'timestamp': '2024-06-15T10:00:00',
                'cpu': {'percent': 45.5},
                'memory': {'percent': 60.0},
                'disk': {'percent': 70.0},
            }
            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                save_metrics_history(metrics)

            assert tmp_file.exists()
            data = json.loads(tmp_file.read_text(encoding='utf-8'))
            assert len(data) == 1
            assert data[0]['t'] == '2024-06-15T10:00:00'
            assert data[0]['cpu'] == 45.5
            assert data[0]['mem'] == 60.0
            assert data[0]['disk'] == 70.0

    def test_appends_to_existing_history(self):
        """اختبار الإضافة إلى سجل موجود"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            existing = [{'t': '2024-01-01T00:00:00', 'cpu': 10, 'mem': 20, 'disk': 30}]
            tmp_file.write_text(json.dumps(existing), encoding='utf-8')

            new_metrics = {
                'timestamp': '2024-06-15T12:00:00',
                'cpu': {'percent': 55.0},
                'memory': {'percent': 65.0},
                'disk': {'percent': 75.0},
            }
            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                save_metrics_history(new_metrics)

            data = json.loads(tmp_file.read_text(encoding='utf-8'))
            assert len(data) == 2
            assert data[1]['t'] == '2024-06-15T12:00:00'

    def test_trims_history_to_max(self):
        """اختبار تقليم السجل لأقصى حد"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            existing = [
                {'t': f'2024-01-01T{i:02d}:00:00', 'cpu': 10, 'mem': 20, 'disk': 30}
                for i in range(24)
            ]
            tmp_file.write_text(json.dumps(existing), encoding='utf-8')

            new_metrics = {
                'timestamp': '2024-06-15T12:00:00',
                'cpu': {'percent': 55.0},
                'memory': {'percent': 65.0},
                'disk': {'percent': 75.0},
            }
            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                with patch('deployment.monitoring.MAX_HISTORY', 25):
                    save_metrics_history(new_metrics)

            data = json.loads(tmp_file.read_text(encoding='utf-8'))
            assert len(data) == 25

    def test_handles_corrupted_history_file(self):
        """اختبار التعامل مع ملف سجل تالف"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            tmp_file.write_text('NOT VALID JSON{{{{', encoding='utf-8')

            metrics = {
                'timestamp': '2024-06-15T10:00:00',
                'cpu': {'percent': 45.5},
                'memory': {'percent': 60.0},
                'disk': {'percent': 70.0},
            }
            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                save_metrics_history(metrics)

            assert tmp_file.exists()

    def test_record_structure_is_correct(self):
        """اختبار هيكل السجل المحفوظ"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            metrics = {
                'timestamp': '2024-06-15T10:00:00',
                'cpu': {'percent': 45.5},
                'memory': {'percent': 60.0},
                'disk': {'percent': 70.0},
            }
            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                save_metrics_history(metrics)

            data = json.loads(tmp_file.read_text(encoding='utf-8'))
            record = data[0]
            assert set(record.keys()) == {'t', 'cpu', 'mem', 'disk'}

    def test_multiple_saves_increase_count(self):
        """اختبار أن الحفظ المتعدد يزيد عدد السجلات"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            metrics = {
                'timestamp': '2024-06-15T10:00:00',
                'cpu': {'percent': 45.5},
                'memory': {'percent': 60.0},
                'disk': {'percent': 70.0},
            }
            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                save_metrics_history(metrics)
                save_metrics_history(metrics)
                save_metrics_history(metrics)

            data = json.loads(tmp_file.read_text(encoding='utf-8'))
            assert len(data) == 3


# ============================================================
# اختبارات get_metrics_history()
# ============================================================


class TestGetMetricsHistory:
    """اختبار دالة جلب سجل المقاييس"""

    def test_returns_empty_when_no_file(self):
        """اختبار إرجاع قائمة فارغة عند عدم وجود ملف"""
        with patch('deployment.monitoring.METRICS_FILE') as mock_file:
            mock_file.exists.return_value = False
            result = get_metrics_history()
            assert result == []

    def test_filters_by_hours(self):
        """اختبار تصفية السجل حسب عدد الساعات"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            now = datetime.now()
            history = [
                {'t': (now - timedelta(minutes=30)).isoformat(), 'cpu': 10},
                {'t': (now - timedelta(hours=3)).isoformat(), 'cpu': 20},
                {'t': (now - timedelta(hours=25)).isoformat(), 'cpu': 30},
            ]
            tmp_file.write_text(json.dumps(history), encoding='utf-8')

            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                result_1h = get_metrics_history(hours=1)
                assert len(result_1h) == 1

                result_24h = get_metrics_history(hours=24)
                assert len(result_24h) == 2

    def test_handles_corrupted_file(self):
        """اختبار التعامل مع ملف تالف"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            tmp_file.write_text('invalid json!!!', encoding='utf-8')
            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                result = get_metrics_history()
                assert result == []

    def test_default_hours_is_one(self):
        """اختبار أن القيمة الافتراضية للساعات هي 1"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            now = datetime.now()
            history = [
                {'t': (now - timedelta(minutes=30)).isoformat(), 'cpu': 10},
                {'t': (now - timedelta(hours=5)).isoformat(), 'cpu': 20},
            ]
            tmp_file.write_text(json.dumps(history), encoding='utf-8')

            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                result = get_metrics_history()
                assert len(result) == 1

    def test_empty_history_file(self):
        """اختبار التعامل مع ملف سجل فارغ"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / 'metrics_history.json'
            tmp_file.write_text('[]', encoding='utf-8')

            with patch('deployment.monitoring.METRICS_FILE', tmp_file):
                result = get_metrics_history()
                assert result == []


# ============================================================
# اختبارات get_service_status()
# ============================================================


class TestGetServiceStatus:
    """اختبار دالة حالة الخدمة"""

    def test_defaults_when_no_state_file(self):
        """اختبار القيم الافتراضية عند عدم وجود ملف"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('deployment.monitoring.BASE_DIR', Path(tmpdir)):
                result = get_service_status()

        assert result['consecutive_failures'] == 0
        assert result['total_restarts'] == 0
        assert result['last_healthy'] is None
        assert result['last_restart'] is None
        assert result['last_check'] is None

    def test_reads_state_from_file(self):
        """اختبار قراءة الحالة من الملف"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            state_file = base / 'deployment' / 'health_state.json'
            state_file.parent.mkdir(parents=True)
            state_data = {
                'consecutive_failures': 3,
                'total_restarts': 5,
                'last_healthy': '2024-06-15T10:00:00',
                'last_restart': '2024-06-15T09:00:00',
                'last_check': '2024-06-15T11:00:00',
            }
            state_file.write_text(json.dumps(state_data), encoding='utf-8')

            with patch('deployment.monitoring.BASE_DIR', base):
                result = get_service_status()

        assert result['consecutive_failures'] == 3
        assert result['total_restarts'] == 5
        assert result['last_healthy'] == '2024-06-15T10:00:00'
        assert result['last_restart'] == '2024-06-15T09:00:00'
        assert result['last_check'] == '2024-06-15T11:00:00'

    def test_handles_corrupted_state_file(self):
        """اختبار التعامل مع ملف حالة تالف"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            state_file = base / 'deployment' / 'health_state.json'
            state_file.parent.mkdir(parents=True)
            state_file.write_text('bad json!!!', encoding='utf-8')

            with patch('deployment.monitoring.BASE_DIR', base):
                result = get_service_status()

        assert result['consecutive_failures'] == 0
        assert result['total_restarts'] == 0

    def test_returns_all_expected_keys(self):
        """اختبار وجود جميع المفاتيح المتوقعة"""
        result = get_service_status()
        expected_keys = {
            'consecutive_failures', 'total_restarts', 'last_healthy',
            'last_restart', 'last_check',
        }
        assert set(result.keys()) == expected_keys

    def test_partial_state_file(self):
        """اختبار ملف حالة يحتوي على أجزاء فقط من البيانات"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            state_file = base / 'deployment' / 'health_state.json'
            state_file.parent.mkdir(parents=True)
            partial_data = {'consecutive_failures': 2}
            state_file.write_text(json.dumps(partial_data), encoding='utf-8')

            with patch('deployment.monitoring.BASE_DIR', base):
                result = get_service_status()

        assert result['consecutive_failures'] == 2
        assert result['total_restarts'] == 0
        assert result['last_healthy'] is None


# ============================================================
# اختبارات API endpoints (views)
# ============================================================


@pytest.mark.django_db
class TestMonitoringDashboardView:
    """اختبار شاشة لوحة المراقبة"""

    def test_dashboard_accessible_without_login(self):
        """اختبار أن اللوحة متاحة بدون تسجيل دخول"""
        client = Client()
        resp = client.get('/monitoring/')
        assert resp.status_code == 200

    def test_dashboard_accessible_for_admin(self):
        """اختبار وصول المسؤول للوحة"""
        admin = User.objects.create_superuser('admin_mon', 'mon@test.com', 'admin123')
        client = Client()
        client.force_login(admin)
        resp = client.get('/monitoring/')
        assert resp.status_code == 200

    def test_post_method_not_allowed(self):
        """اختبار رفض طلب POST"""
        client = Client()
        resp = client.post('/monitoring/')
        assert resp.status_code == 405

    def test_uses_correct_template(self):
        """اختبار استخدام القالب الصحيح"""
        client = Client()
        resp = client.get('/monitoring/')
        assert resp.context['page_title'] == 'لوحة المراقبة'


@pytest.mark.django_db
class TestMonitoringApiMetrics:
    """اختبار نقطة وصول api/metrics"""

    def test_metrics_returns_json_200(self):
        """اختبار إرجاع مقاييس بصيغة JSON مع رمز 200"""
        client = Client()
        resp = client.get('/monitoring/api/metrics/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        for key in ['timestamp', 'cpu', 'memory', 'disk']:
            assert key in data

    def test_metrics_accessible_without_login(self):
        """اختبار أن النقطة متاحة بدون تسجيل دخول"""
        client = Client()
        resp = client.get('/monitoring/api/metrics/')
        assert resp.status_code == 200

    def test_metrics_saves_history(self):
        """اختبار حفظ المقاييس في السجل"""
        client = Client()
        with patch('accounting_system.views.save_metrics_history') as mock_save:
            client.get('/monitoring/api/metrics/')
            mock_save.assert_called_once()

    def test_metrics_cpu_section_structure(self):
        """اختبار هيكل قسم المعالج في الاستجابة"""
        client = Client()
        resp = client.get('/monitoring/api/metrics/')
        data = json.loads(resp.content)
        assert 'percent' in data['cpu']
        assert isinstance(data['cpu']['percent'], (int, float))

    def test_post_not_allowed_metrics(self):
        """اختبار رفض POST على نقطة api/metrics"""
        client = Client()
        resp = client.post('/monitoring/api/metrics/')
        assert resp.status_code == 405


@pytest.mark.django_db
class TestMonitoringApiHistory:
    """اختبار نقطة وصول api/history"""

    def test_history_returns_json_200(self):
        """اختبار إرجاع سجل بصيغة JSON مع رمز 200"""
        client = Client()
        resp = client.get('/monitoring/api/history/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'history' in data
        assert 'hours' in data

    def test_history_accepts_hours_param(self):
        """اختبار قبول معامل الساعات"""
        client = Client()
        resp = client.get('/monitoring/api/history/?hours=24')
        data = json.loads(resp.content)
        assert data['hours'] == 24

    def test_history_default_hours(self):
        """اختبار القيمة الافتراضية للساعات"""
        client = Client()
        resp = client.get('/monitoring/api/history/')
        data = json.loads(resp.content)
        assert data['hours'] == 1

    def test_history_returns_list(self):
        """اختبار إرجاع قائمة في مفتاح history"""
        client = Client()
        resp = client.get('/monitoring/api/history/')
        data = json.loads(resp.content)
        assert isinstance(data['history'], list)

    def test_post_not_allowed_history(self):
        """اختبار رفض POST على نقطة api/history"""
        client = Client()
        resp = client.post('/monitoring/api/history/')
        assert resp.status_code == 405


@pytest.mark.django_db
class TestMonitoringApiStatus:
    """اختبار نقطة وصول api/status"""

    def test_status_returns_json_200(self):
        """اختبار إرجاع حالة بصيغة JSON مع رمز 200"""
        client = Client()
        resp = client.get('/monitoring/api/status/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'consecutive_failures' in data
        assert 'total_restarts' in data

    def test_status_accessible_without_login(self):
        """اختبار أن النقطة متاحة بدون تسجيل دخول"""
        client = Client()
        resp = client.get('/monitoring/api/status/')
        assert resp.status_code == 200

    def test_status_returns_all_keys(self):
        """اختبار وجود جميع مفاتيح الحالة"""
        client = Client()
        resp = client.get('/monitoring/api/status/')
        data = json.loads(resp.content)
        expected = {'consecutive_failures', 'total_restarts', 'last_healthy', 'last_restart', 'last_check'}
        assert set(data.keys()) == expected

    def test_post_not_allowed_status(self):
        """اختبار رفض POST على نقطة api/status"""
        client = Client()
        resp = client.post('/monitoring/api/status/')
        assert resp.status_code == 405
