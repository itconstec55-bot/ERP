from django import forms
from django.core.exceptions import ValidationError
from .models import Bank, Safe, BankTransaction, SafeTransaction


def _validate_non_negative(value, field_name):
    if value is not None and value < 0:
        raise ValidationError(f'لا يمكن أن يكون {field_name} قيمة سالبة.')
    return value


class BankForm(forms.ModelForm):
    class Meta:
        model = Bank
        fields = ['name', 'branch', 'account_number', 'iban', 'swift_code',
                  'account', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class SafeForm(forms.ModelForm):
    class Meta:
        model = Safe
        fields = ['name', 'responsible_person', 'account', 'maximum_limit', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_maximum_limit(self):
        return _validate_non_negative(self.cleaned_data.get('maximum_limit'), 'الحد الأقصى')


class BankTransactionForm(forms.ModelForm):
    class Meta:
        model = BankTransaction
        fields = ['transaction_type', 'date', 'amount', 'reference_number',
                  'check_number', 'description', 'counterparty_account']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['counterparty_account'].required = False
        self.fields['counterparty_account'].label = 'حساب الطرف المقابل'
        self.fields['counterparty_account'].help_text = 'الحساب المحاسبي المقابل (مدين للسحب / دائن للإيداع)'

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError('يجب أن يكون مبلغ المعاملة أكبر من صفر.')
        return amount


class SafeTransactionForm(forms.ModelForm):
    class Meta:
        model = SafeTransaction
        fields = ['transaction_type', 'date', 'amount', 'description', 'counterparty_account']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['counterparty_account'].required = False
        self.fields['counterparty_account'].label = 'حساب الطرف المقابل'
        self.fields['counterparty_account'].help_text = 'الحساب المحاسبي المقابل (مدين للسحب / دائن للإيداع)'

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError('يجب أن يكون مبلغ المعاملة أكبر من صفر.')
        return amount
