from django import forms
from django.core.exceptions import ValidationError

from .models import PaymentReceipt


class PaymentReceiptForm(forms.ModelForm):
    class Meta:
        model = PaymentReceipt
        fields = [
            'receipt_number',
            'receipt_type',
            'date',
            'amount',
            'payment_method',
            'customer',
            'supplier',
            'invoice',
            'purchase_invoice',
            'bank',
            'safe',
            'cheque_number',
            'description',
        ]
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}), 'description': forms.Textarea(attrs={'rows': 3})}

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise ValidationError('يجب أن يكون مبلغ السند أكبر من صفر.')
        return amount

    def clean(self):
        cleaned = super().clean()
        receipt_type = cleaned.get('receipt_type')
        if receipt_type == 'receipt' and not cleaned.get('customer'):
            self.add_error('customer', 'سند القبض يتطلب تحديد عميل.')
        if receipt_type == 'payment' and not cleaned.get('supplier'):
            self.add_error('supplier', 'سند الدفع يتطلب تحديد مورد.')
        return cleaned
