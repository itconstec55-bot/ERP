from django import forms
from django.forms import inlineformset_factory
from .models import (
    Contractor, Contract, ContractItem, InterimCertificate,
    CertificateItem, ContractorPayment
)


class ContractorForm(forms.ModelForm):
    class Meta:
        model = Contractor
        fields = [
            'code', 'name', 'contractor_type', 'tax_number', 'commercial_register',
            'phone', 'email', 'address', 'speciality', 'credit_limit',
            'retention_rate', 'status', 'is_active', 'account', 'notes',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'contractor_type': forms.Select(attrs={'class': 'form-select'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'commercial_register': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'speciality': forms.TextInput(attrs={'class': 'form-control'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'retention_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'account': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ContractorFilterForm(forms.Form):
    search = forms.CharField(required=False, label='بحث', widget=forms.TextInput(attrs={'class': 'form-control'}))
    status = forms.ChoiceField(
        choices=[('', 'الكل')] + Contractor.STATUS_CHOICES,
        required=False, label='الحالة',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    contractor_type = forms.ChoiceField(
        choices=[('', 'الكل')] + Contractor.CONTRACTOR_TYPES,
        required=False, label='النوع',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            'title', 'contractor', 'contract_type', 'contract_amount',
            'vat_rate', 'retention_rate', 'advance_payment_percent',
            'start_date', 'end_date', 'cost_account',
            'penalties_clause', 'special_conditions', 'notes',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'contractor': forms.Select(attrs={'class': 'form-select'}),
            'contract_type': forms.Select(attrs={'class': 'form-select'}),
            'contract_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vat_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'retention_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'advance_payment_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cost_account': forms.Select(attrs={'class': 'form-select'}),
            'penalties_clause': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'special_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ContractFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'الكل')] + Contract.STATUS_CHOICES,
        required=False, label='الحالة',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    contractor = forms.ModelChoiceField(
        queryset=Contractor.objects.filter(is_active=True),
        required=False, label='المقاول',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class ContractItemForm(forms.ModelForm):
    class Meta:
        model = ContractItem
        fields = ['item_number', 'description', 'unit', 'quantity', 'unit_price', 'order']
        widgets = {
            'item_number': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


ContractItemFormSet = inlineformset_factory(
    Contract, ContractItem,
    fields=['item_number', 'description', 'unit', 'quantity', 'unit_price', 'order'],
    extra=3, can_delete=True,
)


class InterimCertificateForm(forms.ModelForm):
    class Meta:
        model = InterimCertificate
        fields = [
            'contract', 'period_number', 'previous_amount', 'current_amount',
            'period_from', 'period_to', 'notes',
        ]
        widgets = {
            'contract': forms.Select(attrs={'class': 'form-select'}),
            'period_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'previous_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'current_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'period_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'period_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class CertificateItemForm(forms.ModelForm):
    class Meta:
        model = CertificateItem
        fields = ['contract_item', 'previous_quantity', 'current_quantity']
        widgets = {
            'contract_item': forms.Select(attrs={'class': 'form-select'}),
            'previous_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'current_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
        }


CertificateItemFormSet = inlineformset_factory(
    InterimCertificate, CertificateItem,
    fields=['contract_item', 'previous_quantity', 'current_quantity'],
    extra=2, can_delete=True,
)


class ContractorPaymentForm(forms.ModelForm):
    class Meta:
        model = ContractorPayment
        fields = [
            'contract', 'certificate', 'amount', 'payment_method',
            'payment_date', 'check_number', 'bank_reference', 'notes',
        ]
        widgets = {
            'contract': forms.Select(attrs={'class': 'form-select'}),
            'certificate': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'check_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
