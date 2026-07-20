from django import forms
from django.core.exceptions import ValidationError
from .models import Cheque


class ChequeForm(forms.ModelForm):
    class Meta:
        model = Cheque
        fields = [
            'cheque_number', 'cheque_type', 'bank_name', 'branch',
            'amount', 'currency', 'issue_date', 'due_date', 'payee_name', 'notes',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise ValidationError('يجب أن يكون مبلغ الشيك أكبر من صفر.')
        return amount

    def clean(self):
        cleaned = super().clean()
        issue_date = cleaned.get('issue_date')
        due_date = cleaned.get('due_date')
        if issue_date and due_date and due_date < issue_date:
            self.add_error('due_date', 'تاريخ الاستحقاق يجب ألا يكون قبل تاريخ الإصدار.')
        return cleaned
