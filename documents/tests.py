import pytest
from datetime import date
from documents.models import DocumentType, DocumentTemplate, Document


@pytest.mark.django_db
class TestDocumentType:
    def test_create(self):
        dt = DocumentType.objects.create(
            code='INV',
            name='فاتورة',
            prefix='INV',
        )
        assert dt.pk is not None
        assert str(dt) == 'INV - فاتورة'

    def test_generate_number(self):
        dt = DocumentType.objects.create(
            code='PO',
            name='أمر شراء',
            prefix='PO',
            next_number=1,
        )
        num = dt.generate_number()
        assert num == 'PO-0001'
        dt.refresh_from_db()
        assert dt.next_number == 2


@pytest.mark.django_db
class TestDocument:
    def test_create(self):
        dt = DocumentType.objects.create(code='CNT', name='عقد', prefix='CNT')
        doc = Document.objects.create(
            document_number='DOC-001',
            document_type=dt,
            title='عقد صيانة',
            date=date(2026, 7, 20),
        )
        assert doc.pk is not None
        assert doc.status == 'draft'

    def test_str(self):
        dt = DocumentType.objects.create(code='RPT', name='تقرير', prefix='RPT')
        doc = Document.objects.create(
            document_number='DOC-002',
            document_type=dt,
            title='تقرير مالي',
            date=date(2026, 7, 20),
        )
        assert 'DOC-002' in str(doc) or 'تقرير' in str(doc)
