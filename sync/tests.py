import pytest
from sync.models import MachineInfo, SyncLog, SyncSettings


@pytest.mark.django_db
class TestMachineInfo:
    def test_create(self):
        m = MachineInfo.objects.create(
            machine_id='MACHINE-TEST1',
            name='جهاز اختبار',
            machine_type='standalone',
        )
        assert m.pk is not None
        assert 'اختبار' in str(m)
        assert m.is_active is True

    def test_auto_generate_api_key(self):
        m = MachineInfo.objects.create(
            name='جهاز بدون مفتاح',
            machine_type='standalone',
        )
        assert len(m.api_key) == 64

    def test_test_connection(self):
        m = MachineInfo.objects.create(
            machine_id='MACHINE-TEST2',
            name='جهاز اتصال',
            machine_type='host',
        )
        result = m.test_connection()
        assert result['machine_id'] == 'MACHINE-TEST2'
        assert result['is_active'] is True


@pytest.mark.django_db
class TestSyncLog:
    def test_create(self):
        source = MachineInfo.objects.create(
            machine_id='MACHINE-SRC',
            name='مصدر', machine_type='host',
        )
        log = SyncLog.objects.create(
            source_machine=source,
            sync_type='full',
            status='completed',
            records_sent=10,
        )
        assert log.pk is not None
        assert log.status == 'completed'


@pytest.mark.django_db
class TestSyncSettings:
    def test_get_settings_singleton(self):
        s = SyncSettings.get_settings()
        assert s.pk is not None

    def test_defaults(self):
        s = SyncSettings.get_settings()
        assert s.auto_sync_enabled is False
        assert s.sync_interval_minutes == 5
