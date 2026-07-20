from django import forms

from purchases.models import Product, Supplier

from .models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['order_number', 'supplier', 'cost_center', 'date', 'expected_date', 'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'order_number': forms.TextInput(attrs={'placeholder': 'يُولَّد تلقائياً عند الحفظ'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
        self.fields['order_number'].required = False


class PurchaseOrderLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ['product', 'quantity', 'unit_price', 'received_quantity', 'notes']

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

    def clean_received_quantity(self):
        received = self.cleaned_data.get('received_quantity', 0) or 0
        if received < 0:
            raise forms.ValidationError('الكمية المستلمة لا يمكن أن تكون سالبة')
        return received


PurchaseOrderLineFormSet = forms.inlineformset_factory(
    PurchaseOrder, PurchaseOrderLine, form=PurchaseOrderLineForm, extra=3, can_delete=True, min_num=1, validate_min=True
)
