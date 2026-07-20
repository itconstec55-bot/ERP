from django import forms
from django.core.exceptions import ValidationError
from .models import ReconciliationSession, BankStatementItem


class ReconciliationSessionForm(forms.ModelForm):
    class Meta:
        model = ReconciliationSession
        fields = [
            'bank_account', 'period_start', 'period_end',
            'book_balance', 'bank_balance',
        ]
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('period_start')
        end = cleaned.get('period_end')
        if start and end and end < start:
            self.add_error('period_end', 'تاريخ النهاية يجب ألا يكون قبل تاريخ البداية.')
        return cleaned


class BankStatementItemForm(forms.ModelForm):
    class Meta:
        model = BankStatementItem
        fields = [
            'bank_account', 'transaction_date', 'description',
            'reference', 'debit_amount', 'credit_amount',
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_debit_amount(self):
        amount = self.cleaned_data.get('debit_amount') or 0
        if amount < 0:
            raise ValidationError('المبلغ المدين يجب ألا يكون سالباً.')
        return amount

    def clean_credit_amount(self):
        amount = self.cleaned_data.get('credit_amount') or 0
        if amount < 0:
            raise ValidationError('المبلغ الدائن يجب ألا يكون سالباً.')
        return amount
