from django import forms
from .models import Company, CompanyBranch
from accounts.models import Account


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            'name', 'name_en', 'address', 'city', 'country',
            'phone', 'mobile', 'fax', 'email', 'website',
            'tax_number', 'commercial_register', 'company_number',
            'logo', 'currency', 'currency_code', 'vat_rate',
            'fiscal_year_start', 'fiscal_year_end',
            'bank_name', 'bank_account_number', 'bank_iban', 'bank_swift',
            'registration_notes',
            # حسابات محاسبية
            'purchases_account', 'vat_account', 'withholding_tax_account',
            'supplier_account', 'customer_account', 'sales_revenue_account',
            'cogs_account', 'inventory_account',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'fax': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'commercial_register': forms.TextInput(attrs={'class': 'form-control'}),
            'company_number': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'currency_code': forms.TextInput(attrs={'class': 'form-control'}),
            'vat_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fiscal_year_start': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MM-DD'}),
            'fiscal_year_end': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MM-DD'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_iban': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_swift': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            # حسابات محاسبية
            'purchases_account': forms.Select(attrs={'class': 'form-select'}),
            'vat_account': forms.Select(attrs={'class': 'form-select'}),
            'withholding_tax_account': forms.Select(attrs={'class': 'form-select'}),
            'supplier_account': forms.Select(attrs={'class': 'form-select'}),
            'customer_account': forms.Select(attrs={'class': 'form-select'}),
            'sales_revenue_account': forms.Select(attrs={'class': 'form-select'}),
            'cogs_account': forms.Select(attrs={'class': 'form-select'}),
            'inventory_account': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # فلترة الحسابات النشطة فقط
        active_accounts = Account.objects.filter(is_active=True).order_by('code')
        for field_name in [
            'purchases_account', 'vat_account', 'withholding_tax_account',
            'supplier_account', 'customer_account', 'sales_revenue_account',
            'cogs_account', 'inventory_account'
        ]:
            self.fields[field_name].queryset = active_accounts
            self.fields[field_name].required = False
            self.fields[field_name].empty_label = '— اختر حساب —'


class CompanyBranchForm(forms.ModelForm):
    class Meta:
        model = CompanyBranch
        fields = ['name', 'address', 'city', 'phone', 'manager', 'is_active', 'is_default']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'manager': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
