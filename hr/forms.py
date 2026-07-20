from django import forms
from django.core.exceptions import ValidationError
from .models import Employee, Department, Attendance, Salary, Contract, LeaveType, LeaveRequest


def _validate_salary(value, field_name):
    if value is not None and value < 0:
        raise ValidationError(f'لا يمكن أن يكون {field_name} قيمة سالبة.')
    return value


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['employee_number', 'first_name', 'last_name', 'national_id',
                  'gender', 'date_of_birth', 'marital_status', 'department',
                  'position', 'hire_date', 'phone', 'mobile', 'email', 'address',
                  'salary', 'social_insurance_number', 'tax_number', 'bank_account',
                  'account', 'notes']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_salary(self):
        return _validate_salary(self.cleaned_data.get('salary'), 'الراتب')


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'manager', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'check_in', 'check_out', 'status',
                  'overtime_hours', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'check_in': forms.TimeInput(attrs={'type': 'time'}),
            'check_out': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class SalaryForm(forms.ModelForm):
    MONETARY_FIELDS = ['basic_salary', 'allowances', 'overtime', 'bonus',
                       'deductions', 'social_insurance', 'income_tax']

    class Meta:
        model = Salary
        fields = ['employee', 'month', 'year', 'basic_salary', 'allowances',
                  'overtime', 'bonus', 'deductions', 'social_insurance',
                  'income_tax', 'payment_date', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        for field in self.MONETARY_FIELDS:
            value = cleaned.get(field)
            if value is not None and value < 0:
                self.add_error(field, f'لا يمكن أن يكون {self.fields[field].label} قيمة سالبة.')
        return cleaned


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ['employee', 'contract_number', 'contract_type', 'start_date', 'end_date',
                  'salary', 'probation_period_months', 'annual_leave_days', 'notice_period_days', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['name', 'days_per_year', 'is_paid']


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'days', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }
