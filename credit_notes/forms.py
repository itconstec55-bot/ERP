from django import forms
from .models import CreditNote


class CreditNoteForm(forms.ModelForm):
    class Meta:
        model = CreditNote
        fields = [
            'note_type', 'note_number', 'date', 'customer', 'supplier',
            'original_invoice_number', 'original_sales_invoice', 'original_purchase_invoice',
            'subtotal', 'vat_amount', 'reason', 'notes',
        ]
        widgets = {
            'note_type': forms.Select(attrs={'class': 'form-select', 'id': 'noteType', 'onchange': 'toggleParties()'}),
            'note_number': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'original_invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'original_sales_invoice': forms.Select(attrs={'class': 'form-select', 'id': 'salesInvoiceSelect'}),
            'original_purchase_invoice': forms.Select(attrs={'class': 'form-select', 'id': 'purchaseInvoiceSelect'}),
            'subtotal': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vat_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
