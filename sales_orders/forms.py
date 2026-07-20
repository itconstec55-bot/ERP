from django import forms

from purchases.models import Product
from sales.models import Customer

from .models import SalesOrder, SalesOrderLine


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ['order_number', 'customer', 'date', 'expected_date', 'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'order_number': forms.TextInput(attrs={'placeholder': 'يُولَّد تلقائياً عند الحفظ'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        self.fields['order_number'].required = False


class SalesOrderLineForm(forms.ModelForm):
    class Meta:
        model = SalesOrderLine
        fields = ['product', 'quantity', 'unit_price', 'invoiced_quantity', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity', 0)
        if qty is None or qty <= 0:
            raise forms.ValidationError('الكمية يجب أن تكون أكبر من صفر')
        return qty

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price', 0)
        if price is None or price < 0:
            raise forms.ValidationError('السعر لا يمكن أن يكون سالباً')
        return price

    def clean_invoiced_quantity(self):
        invoiced = self.cleaned_data.get('invoiced_quantity', 0) or 0
        if invoiced < 0:
            raise forms.ValidationError('الكمية المفوترة لا يمكن أن تكون سالبة')
        return invoiced


SalesOrderLineFormSet = forms.inlineformset_factory(
    SalesOrder, SalesOrderLine, form=SalesOrderLineForm, extra=3, can_delete=True, min_num=1, validate_min=True
)
