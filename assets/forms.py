from django import forms
from django.core.exceptions import ValidationError
from .models import Asset, AssetCategory, DepreciationEntry


def _non_negative(value, field_name):
    if value is not None and value < 0:
        raise ValidationError(f'لا يمكن أن يكون {field_name} قيمة سالبة.')
    return value


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['code', 'name', 'category', 'description', 'purchase_date',
                  'purchase_price', 'salvage_value', 'useful_life_years',
                  'depreciation_method', 'location', 'asset_account', 'depr_account']
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_purchase_price(self):
        return _non_negative(self.cleaned_data.get('purchase_price'), 'سعر الشراء')

    def clean_salvage_value(self):
        return _non_negative(self.cleaned_data.get('salvage_value'), 'القيمة التخريدية')

    def clean_useful_life_years(self):
        years = self.cleaned_data.get('useful_life_years')
        if years is not None and years <= 0:
            raise ValidationError('يجب أن تكون السنوات المفيدة أكبر من صفر.')
        return years

    def clean(self):
        cleaned_data = super().clean()
        purchase_price = cleaned_data.get('purchase_price')
        salvage_value = cleaned_data.get('salvage_value')
        if purchase_price and salvage_value and salvage_value > purchase_price:
            raise ValidationError('القيمة التخريدية لا يمكن أن تتجاوز سعر الشراء.')
        return cleaned_data


class AssetCategoryForm(forms.ModelForm):
    class Meta:
        model = AssetCategory
        fields = ['name', 'depreciation_rate', 'account', 'depreciation_account']

    def clean_depreciation_rate(self):
        rate = self.cleaned_data.get('depreciation_rate')
        if rate is not None and (rate < 0 or rate > 100):
            raise ValidationError('يجب أن يكون معدل الإهلاك بين 0 و 100.')
        return rate


class DepreciationEntryForm(forms.ModelForm):
    class Meta:
        model = DepreciationEntry
        fields = ['date', 'months', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_months(self):
        months = self.cleaned_data.get('months')
        if months is not None and months <= 0:
            raise ValidationError('يجب أن يكون عدد الأشهر أكبر من صفر.')
        return months
