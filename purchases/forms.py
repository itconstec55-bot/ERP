from django import forms
from django.utils import timezone

from .models import (
    CatalogSettings,
    Product,
    ProductCategory,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    Supplier,
    UnitOfMeasure,
)


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            'code',
            'name',
            'supplier_type',
            'tax_number',
            'commercial_register',
            'address',
            'city',
            'phone',
            'mobile',
            'email',
            'account',
            'credit_limit',
            'notes',
        ]
        widgets = {'address': forms.Textarea(attrs={'rows': 3}), 'notes': forms.Textarea(attrs={'rows': 3})}

    def clean_credit_limit(self):
        limit = self.cleaned_data.get('credit_limit', 0)
        if limit < 0:
            raise forms.ValidationError('حد الائتمان لا يمكن أن يكون سالباً')
        return limit


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'code',
            'name',
            'category',
            'unit_of_measure',
            'description',
            'purchase_price',
            'selling_price',
            'current_stock',
            'minimum_stock',
            'vat_rate',
        ]
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_of_measure'].queryset = UnitOfMeasure.objects.filter(is_active=True)
        self.fields['unit_of_measure'].required = False

    def clean(self):
        cleaned = super().clean()
        purchase = cleaned.get('purchase_price', 0) or 0
        selling = cleaned.get('selling_price', 0) or 0
        if purchase < 0:
            raise forms.ValidationError('سعر الشراء لا يمكن أن يكون سالباً')
        if selling < 0:
            raise forms.ValidationError('سعر البيع لا يمكن أن يكون سالباً')
        settings = CatalogSettings.get_settings()
        if settings.enforce_unit and not cleaned.get('unit_of_measure'):
            raise forms.ValidationError('يجب تحديد وحدة القياس للمنتج حسب إعدادات الكتالوج')
        if settings.enforce_category and not cleaned.get('category'):
            raise forms.ValidationError('يجب تحديد التصنيف للمنتج حسب إعدادات الكتالوج')
        return cleaned


class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ['code', 'name', 'parent', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = ProductCategory.objects.exclude(pk=self.instance.pk)


class UnitOfMeasureForm(forms.ModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = ['code', 'name', 'symbol', 'base_unit', 'conversion_factor', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['base_unit'].queryset = UnitOfMeasure.objects.exclude(pk=self.instance.pk)


class CatalogSettingsForm(forms.ModelForm):
    class Meta:
        model = CatalogSettings
        fields = ['default_unit', 'default_category', 'enforce_unit', 'enforce_category', 'allow_decimal_quantity']


class PurchaseInvoiceForm(forms.ModelForm):
    class Meta:
        model = PurchaseInvoice
        fields = [
            'invoice_number',
            'file_number',
            'supplier',
            'date',
            'due_date',
            'payment_method',
            'is_tax_invoice',
            'withholding_tax_type',
            'discount_amount',
            'paid_amount',
            'notes',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'file_number': forms.TextInput(attrs={'placeholder': 'رقم الملف المرجعي (اختياري)'}),
        }

    def clean(self):
        cleaned = super().clean()
        date_val = cleaned.get('date')
        due_date = cleaned.get('due_date')
        if date_val and due_date and due_date < date_val:
            raise forms.ValidationError('تاريخ الاستحقاق لا يمكن أن يكون قبل تاريخ الفاتورة')
        if date_val and date_val > timezone.localdate():
            raise forms.ValidationError('تاريخ الفاتورة لا يمكن أن يكون في المستقبل')
        discount = cleaned.get('discount_amount', 0) or 0
        if discount < 0:
            raise forms.ValidationError('قيمة الخصم لا يمكن أن تكون سالبة')
        paid = cleaned.get('paid_amount', 0) or 0
        if paid < 0:
            raise forms.ValidationError('المبلغ المدفوع لا يمكن أن يكون سالباً')
        return cleaned


class PurchaseInvoiceLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseInvoiceLine
        fields = ['product', 'quantity', 'unit_price', 'discount_percent']

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity', 0)
        if qty <= 0:
            raise forms.ValidationError('الكمية يجب أن تكون أكبر من صفر')
        return qty

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price', 0)
        if price < 0:
            raise forms.ValidationError('السعر لا يمكن أن يكون سالباً')
        return price

    def clean_discount_percent(self):
        disc = self.cleaned_data.get('discount_percent', 0)
        if disc < 0 or disc > 100:
            raise forms.ValidationError('نسبة الخصم يجب أن تكون بين 0 و 100')
        return disc


PurchaseInvoiceLineFormSet = forms.inlineformset_factory(
    PurchaseInvoice,
    PurchaseInvoiceLine,
    form=PurchaseInvoiceLineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
