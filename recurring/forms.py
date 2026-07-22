from django import forms
from django.core.exceptions import ValidationError

from .models import RecurringJournal


class RecurringJournalForm(forms.ModelForm):
    class Meta:
        model = RecurringJournal
        fields = ['name', 'description', 'frequency', 'day_of_month', 'next_due_date', 'journal_type', 'reference']
        widgets = {'next_due_date': forms.DateInput(attrs={'type': 'date'})}

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or not name.strip():
            raise ValidationError('اسم القيد الدوري مطلوب.')
        return name

    def clean_frequency(self):
        frequency = self.cleaned_data.get('frequency')
        if not frequency:
            raise ValidationError('تكرار القيد مطلوب.')
        return frequency

    def clean_day_of_month(self):
        day = self.cleaned_data.get('day_of_month')
        if day is None or day < 1 or day > 31:
            raise ValidationError('يوم الشهر يجب أن يكون بين 1 و 31.')
        return day

    def clean_next_due_date(self):
        due_date = self.cleaned_data.get('next_due_date')
        if due_date is None:
            raise ValidationError('تاريخ الاستحقاق التالي مطلوب.')
        return due_date
