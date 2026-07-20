from django import forms
from django.core.exceptions import ValidationError
from .models import NotificationTemplate


class NotificationTemplateForm(forms.ModelForm):
    class Meta:
        model = NotificationTemplate
        fields = ['name', 'event', 'subject_template', 'body_template', 'is_active']

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or not name.strip():
            raise ValidationError('اسم القالب مطلوب.')
        return name.strip()

    def clean_event(self):
        event = self.cleaned_data.get('event')
        if not event:
            raise ValidationError('يجب اختيار حدث للقالب.')
        return event

    def clean_subject_template(self):
        value = self.cleaned_data.get('subject_template')
        if not value or not value.strip():
            raise ValidationError('قالب الموضوع مطلوب.')
        return value.strip()

    def clean_body_template(self):
        value = self.cleaned_data.get('body_template')
        if not value or not value.strip():
            raise ValidationError('قالب المحتوى مطلوب.')
        return value.strip()
