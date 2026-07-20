from django import forms
from django.core.exceptions import ValidationError
from .models import Currency


class CurrencyForm(forms.ModelForm):
    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol', 'exchange_rate_to_egp', 'is_base', 'is_active']

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code or not code.strip():
            raise ValidationError('كود العملة مطلوب.')
        return code.strip().upper()

    def clean_exchange_rate_to_egp(self):
        rate = self.cleaned_data.get('exchange_rate_to_egp')
        if rate is None or rate <= 0:
            raise ValidationError('سعر الصرف يجب أن يكون أكبر من صفر.')
        return rate
