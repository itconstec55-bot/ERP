from django.contrib import admin

from .models import Attendance, Department, Employee, Salary


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager', 'is_active')
    list_filter = ('is_active',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_number', 'full_name', 'department', 'position', 'salary', 'status')
    list_filter = ('department', 'status', 'gender')
    search_fields = ('employee_number', 'first_name', 'last_name', 'national_id')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'check_in', 'check_out', 'status')
    list_filter = ('status', 'date')
    search_fields = ('employee__first_name', 'employee__last_name')


@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'year', 'basic_salary', 'net_salary', 'is_paid')
    list_filter = ('year', 'month', 'is_paid')
    search_fields = ('employee__first_name', 'employee__last_name')
