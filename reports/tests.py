import pytest

from reports.models import ReportTemplate


@pytest.mark.django_db
class TestReportTemplate:
    def test_create_template(self):
        rt = ReportTemplate.objects.create(name='قائمة الدخل الشهرية', report_type='income_statement')
        assert rt.pk is not None
        assert str(rt) == 'قائمة الدخل الشهرية'
        assert rt.is_active is True

    def test_all_report_types(self):
        for rtype, _ in ReportTemplate.REPORT_TYPE_CHOICES:
            rt = ReportTemplate.objects.create(name=f'تقرير {rtype}', report_type=rtype)
            assert rt.pk is not None
            assert rt.report_type == rtype

    def test_template_description_optional(self):
        rt = ReportTemplate.objects.create(name='تقرير بدون وصف', report_type='balance_sheet')
        assert rt.description is None or rt.description == ''
