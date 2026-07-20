from django import forms
from purchases.models import Product, UnitOfMeasure
from budget.models import CostCenter
from .models import Requisition, RequisitionLine


class RequisitionForm(forms.ModelForm):
    class Meta:
        model = Requisition
        fields = ['cost_center', 'date', 'need_by_date', 'priority', 'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'need_by_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cost_center'].queryset = CostCenter.objects.filter(is_active=True)
        self.fields['cost_center'].required = False


class RequisitionLineForm(forms.ModelForm):
    class Meta:
        model = RequisitionLine
        fields = ['product', 'quantity', 'uom', 'estimated_unit_price', 'required_date', 'notes']
        widgets = {
            'required_date': forms.DateInput(attrs={'type': 'date'}),
            'estimated_unit_price': forms.NumberInput(attrs={'step': '0.0001'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['uom'].queryset = UnitOfMeasure.objects.filter(is_active=True)
        self.fields['uom'].required = False

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity', 0)
        if qty is None or qty <= 0:
            raise forms.ValidationError('الكمية يجب أن تكون أكبر من صفر')
        return qty


RequisitionLineFormSet = forms.inlineformset_factory(
    Requisition, RequisitionLine,
    form=RequisitionLineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
