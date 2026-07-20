from django import forms
from purchases.models import Product, Supplier
from .models import RFQ, RFQLine, Quotation, QuotationLine


class RFQForm(forms.ModelForm):
    class Meta:
        model = RFQ
        fields = ['requisition', 'requested_by', 'cost_center', 'date', 'valid_until', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'requisition': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['requested_by'].required = False
        self.fields['requested_by'].label = 'طالب الشراء'
        self.fields['cost_center'].queryset = self.fields['cost_center'].queryset
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.DateInput) and not isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault('class', 'form-control')


class RFQLineForm(forms.ModelForm):
    class Meta:
        model = RFQLine
        fields = ['product', 'quantity', 'required_date', 'estimated_unit_price', 'description']
        widgets = {
            'required_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.TextInput(attrs={'placeholder': 'وصف حر إن لم يُختر منتج'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].required = True
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.DateInput):
                field.widget.attrs.setdefault('class', 'form-control')

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity', 0)
        if qty is None or qty <= 0:
            raise forms.ValidationError('الكمية يجب أن تكون أكبر من صفر')
        return qty


RFQLineFormSet = forms.inlineformset_factory(
    RFQ, RFQLine,
    form=RFQLineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ['supplier', 'received_date', 'valid_until', 'notes']
        widgets = {
            'received_date': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.DateInput) and not isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault('class', 'form-control')


class QuotationLineForm(forms.ModelForm):
    class Meta:
        model = QuotationLine
        fields = ['rfq_line', 'product', 'quantity', 'unit_price', 'discount', 'delivery_days']
        widgets = {
            'delivery_days': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, rfq=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].required = True
        if rfq is not None:
            self.fields['rfq_line'].queryset = rfq.lines.all()
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-control')

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


QuotationLineFormSet = forms.inlineformset_factory(
    Quotation, QuotationLine,
    form=QuotationLineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
