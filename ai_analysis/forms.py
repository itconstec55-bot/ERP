from django import forms
from .models import ErrorLog


class AccountingErrorForm(forms.Form):
    """نموذج إدخال الخطأ المحاسبي"""
    
    ERROR_TYPE_CHOICES = [
        ('auto', 'كشف تلقائي'),
        ('unbalanced', 'قيد غير متوازن'),
        ('duplicate', 'قيد مكرر'),
        ('reconciliation', 'فرق تسوية'),
        ('account', 'خطأ في الحساب'),
        ('amount', 'خطأ في المبلغ'),
        ('other', 'أخرى'),
    ]
    
    error_type = forms.ChoiceField(
        choices=ERROR_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='نوع الخطأ'
    )
    reference_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='رقم المرجع'
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='من تاريخ'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='إلى تاريخ'
    )
    account_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='كود الحساب'
    )
    amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='المبلغ'
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='الوصف'
    )


class ErrorLogFilterForm(forms.Form):
    """نموذج فلترة سجلات الأخطاء"""
    
    SEVERITY_CHOICES = [
        ('', 'الكل'),
        ('low', 'منخفض'),
        ('medium', 'متوسط'),
        ('high', 'عالي'),
        ('critical', 'حرج'),
    ]
    
    STATUS_CHOICES = [
        ('', 'الكل'),
        ('detected', 'تم الكشف'),
        ('analyzing', 'قيد التحليل'),
        ('resolved', 'تم الحل'),
        ('ignored', 'تجاهل'),
    ]
    
    severity = forms.ChoiceField(
        choices=SEVERITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label='الشدة'
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label='الحالة'
    )
    error_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        label='نوع الخطأ'
    )
