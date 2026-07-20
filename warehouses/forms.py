from django import forms
from django.core.exceptions import ValidationError
from .models import Warehouse, WarehouseProduct, StockMovement


def _non_negative_decimal(value, field_name):
    if value is not None and value < 0:
        raise ValidationError(f'لا يمكن أن يكون {field_name} قيمة سالبة.')
    return value


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ['code', 'name', 'location', 'manager', 'phone', 'notes', 'is_active']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class WarehouseProductForm(forms.ModelForm):
    class Meta:
        model = WarehouseProduct
        fields = ['product', 'quantity', 'minimum_quantity', 'maximum_quantity']

    def clean_quantity(self):
        return _non_negative_decimal(self.cleaned_data.get('quantity'), 'الكمية')

    def clean_minimum_quantity(self):
        return _non_negative_decimal(self.cleaned_data.get('minimum_quantity'), 'الحد الأدنى')

    def clean_maximum_quantity(self):
        return _non_negative_decimal(self.cleaned_data.get('maximum_quantity'), 'الحد الأقصى')

    def clean(self):
        cleaned = super().clean()
        mn = cleaned.get('minimum_quantity')
        mx = cleaned.get('maximum_quantity')
        if mn is not None and mx is not None and mx < mn:
            self.add_error('maximum_quantity', 'الحد الأقصى يجب ألا يقل عن الحد الأدنى.')
        return cleaned


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['movement_type', 'warehouse', 'to_warehouse', 'product', 'quantity',
                  'unit_cost', 'reference_number', 'notes', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty <= 0:
            raise ValidationError('يجب أن تكون الكمية أكبر من صفر.')
        return qty

    def clean_unit_cost(self):
        return _non_negative_decimal(self.cleaned_data.get('unit_cost'), 'تكلفة الوحدة')
