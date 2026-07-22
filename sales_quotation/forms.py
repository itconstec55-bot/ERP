from django import forms

from .models import SalesQuotation, SalesQuotationLine


class SalesQuotationForm(forms.ModelForm):
    class Meta:
        model = SalesQuotation
        fields = ['customer', 'date', 'valid_until', 'payment_terms', 'delivery_terms', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


SalesQuotationLineFormSet = forms.inlineformset_factory(
    SalesQuotation,
    SalesQuotationLine,
    fields=['product', 'description', 'quantity', 'unit_price', 'discount_percent'],
    extra=1,
    can_delete=True,
)
