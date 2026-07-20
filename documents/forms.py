from django import forms
from django.core.exceptions import ValidationError

from .models import Document, DocumentAttachment, DocumentFlow, DocumentTemplate, DocumentType


class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['code', 'name', 'description', 'prefix', 'next_number', 'is_active']


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = ['name', 'document_type', 'content', 'is_default', 'is_active']
        widgets = {'content': forms.Textarea(attrs={'rows': 6})}


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'document_type',
            'title',
            'description',
            'date',
            'due_date',
            'status',
            'priority',
            'department',
            'assigned_to',
            'account',
            'reference_amount',
            'reference_number',
            'notes',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_reference_amount(self):
        amount = self.cleaned_data.get('reference_amount')
        if amount is not None and amount < 0:
            raise ValidationError('لا يمكن أن يكون المبلغ المرجعي قيمة سالبة.')
        return amount


class DocumentFlowForm(forms.ModelForm):
    class Meta:
        model = DocumentFlow
        fields = ['action', 'comment']
        widgets = {'comment': forms.Textarea(attrs={'rows': 3})}


ALLOWED_UPLOAD_TYPES = {
    'application/pdf': 'PDF',
    'image/jpeg': 'JPEG',
    'image/png': 'PNG',
    'image/gif': 'GIF',
    'application/msword': 'Word',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
    'application/vnd.ms-excel': 'Excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
    'text/plain': 'نص',
}
MAX_UPLOAD_SIZE_MB = 10


class DocumentAttachmentForm(forms.ModelForm):
    class Meta:
        model = DocumentAttachment
        fields = ['file', 'name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def clean_file(self):
        f = self.cleaned_data.get('file')
        if f is None:
            return f
        if f.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise ValidationError(f'حجم الملف يتجاوز الحد الأقصى ({MAX_UPLOAD_SIZE_MB} ميجابايت).')
        content_type = getattr(f, 'content_type', None)
        if content_type and content_type not in ALLOWED_UPLOAD_TYPES:
            allowed = ', '.join(ALLOWED_UPLOAD_TYPES.values())
            raise ValidationError(f'نوع الملف غير مدعوم. الأنواع المسموحة: {allowed}')
        return f
