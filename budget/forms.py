from django import forms
from django.core.exceptions import ValidationError

from .models import Budget, CostCenter


class CostCenterForm(forms.ModelForm):
    class Meta:
        model = CostCenter
        fields = ['code', 'name', 'parent', 'manager', 'description']

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code or not code.strip():
            raise ValidationError('كود مركز التكلفة مطلوب.')
        return code

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name or not name.strip():
            raise ValidationError('اسم مركز التكلفة مطلوب.')
        return name


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['name', 'account', 'cost_center', 'period', 'year', 'month', 'budgeted_amount', 'notes']

    def clean_year(self):
        year = self.cleaned_data.get('year')
        if year is None:
            raise ValidationError('السنة مطلوبة.')
        if year < 2000 or year > 2100:
            raise ValidationError('السنة يجب أن تكون بين 2000 و 2100.')
        return year

    def clean_month(self):
        month = self.cleaned_data.get('month')
        if month is not None and (month < 1 or month > 12):
            raise ValidationError('الشهر يجب أن يكون بين 1 و 12.')
        return month

    def clean_budgeted_amount(self):
        amount = self.cleaned_data.get('budgeted_amount')
        if amount is None or amount < 0:
            raise ValidationError('المبلغ المخطط يجب ألا يكون سالباً.')
        return amount
