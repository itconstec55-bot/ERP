from django import forms
from .models import Account, JournalEntry, JournalEntryLine


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['code', 'name', 'account_type', 'parent', 'description',
                  'opening_balance', 'is_bank', 'is_safe', 'tax_account']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if code and not code.isdigit():
            raise forms.ValidationError('كود الحساب يجب أن يتكون من أرقام فقط')
        return code

    def clean_opening_balance(self):
        balance = self.cleaned_data.get('opening_balance', 0)
        if balance < 0:
            raise forms.ValidationError('لا يمكن أن يكون الرصيد الافتتاحي سالباً')
        return balance


class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = ['entry_type', 'date', 'description', 'reference']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_date(self):
        from datetime import date
        d = self.cleaned_data.get('date')
        if d and d > date.today():
            raise forms.ValidationError('لا يمكن أن يكون تاريخ القيد في المستقبل')
        return d


class JournalEntryLineForm(forms.ModelForm):
    class Meta:
        model = JournalEntryLine
        fields = ['account', 'debit', 'credit', 'description']

    def clean(self):
        cleaned = super().clean()
        debit = cleaned.get('debit', 0) or 0
        credit = cleaned.get('credit', 0) or 0
        if debit > 0 and credit > 0:
            raise forms.ValidationError('لا يمكن أن يحتوي السطر على مدين ودائن في نفس الوقت')
        if debit == 0 and credit == 0:
            raise forms.ValidationError('يجب إدخال المبلغ كمدين أو دائن')
        return cleaned


JournalEntryLineFormSet = forms.inlineformset_factory(
    JournalEntry, JournalEntryLine,
    form=JournalEntryLineForm,
    extra=2,
    can_delete=True,
    min_num=2,
    validate_min=True,
)
