from django import forms
from django.utils import timezone

from .models import Customer, SalesInvoice, SalesInvoiceLine


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'code',
            'name',
            'customer_type',
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


class SalesInvoiceForm(forms.ModelForm):
    class Meta:
        model = SalesInvoice
        fields = [
            'invoice_number',
            'file_number',
            'customer',
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


class SalesInvoiceLineForm(forms.ModelForm):
    class Meta:
        model = SalesInvoiceLine
        fields = ['product', 'quantity', 'unit_price', 'cost_price', 'discount_percent']

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


SalesInvoiceLineFormSet = forms.inlineformset_factory(
    SalesInvoice, SalesInvoiceLine, form=SalesInvoiceLineForm, extra=3, can_delete=True, min_num=1, validate_min=True
)
