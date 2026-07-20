from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from common.permissions import screen_permission_required
from common.excel_utils import export_to_excel, import_from_excel
from .models import Employee, Department, Attendance, Salary, Contract, LeaveType, LeaveRequest
from .forms import EmployeeForm, DepartmentForm, AttendanceForm, SalaryForm, ContractForm, LeaveTypeForm, LeaveRequestForm
import logging

logger = logging.getLogger('accounting')


@screen_permission_required('hr.employee', 'view')
def employee_list(request):
    employees = Employee.objects.filter(status='active').select_related('department')
    department = request.GET.get('department')
    if department:
        employees = employees.filter(department_id=department)
    departments = Department.objects.filter(is_active=True)
    return render(request, 'hr/employee_list.html', {
        'employees': employees,
        'departments': departments,
    })


@screen_permission_required('hr.employee', 'add')
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الموظف بنجاح')
            return redirect('hr:employee_list')
    else:
        form = EmployeeForm()
    return render(request, 'hr/employee_form.html', {'form': form})


@screen_permission_required('hr.employee', 'view')
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    attendances = Attendance.objects.filter(employee=employee).order_by('-date')[:30]
    salaries = Salary.objects.filter(employee=employee).order_by('-year', '-month')[:12]
    return render(request, 'hr/employee_detail.html', {
        'employee': employee,
        'attendances': attendances,
        'salaries': salaries,
    })


@screen_permission_required('hr.employee', 'edit')
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل بيانات الموظف بنجاح')
            return redirect('hr:employee_detail', pk=pk)
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'hr/employee_form.html', {'form': form, 'employee': employee})


@screen_permission_required('hr.employee', 'view')
def attendance_list(request):
    attendances = Attendance.objects.select_related('employee').order_by('-date')[:100]
    return render(request, 'hr/attendance_list.html', {'attendances': attendances})


@screen_permission_required('hr.employee', 'add')
def attendance_create(request):
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تسجيل الحضور بنجاح')
            return redirect('hr:attendance_list')
    else:
        form = AttendanceForm()
    return render(request, 'hr/attendance_form.html', {'form': form})


@screen_permission_required('hr.employee', 'view')
def salary_list(request):
    year = request.GET.get('year')
    salaries = Salary.objects.select_related('employee').all()
    if year:
        salaries = salaries.filter(year=year)
    paginator = Paginator(salaries, 25)
    page = request.GET.get('page')
    salaries_page = paginator.get_page(page)
    return render(request, 'hr/salary_list.html', {'salaries': salaries_page})


@screen_permission_required('hr.employee', 'add')
def salary_create(request):
    if request.method == 'POST':
        form = SalaryForm(request.POST)
        if form.is_valid():
            salary = form.save(commit=False)
            salary.created_by = request.user
            salary.calculate_net_salary()
            salary.save()
            messages.success(request, 'تم إنشاء الراتب بنجاح')
            return redirect('hr:salary_list')
    else:
        form = SalaryForm()
    return render(request, 'hr/salary_form.html', {'form': form})


@require_POST
@screen_permission_required('hr.employee', 'edit')
def salary_post(request, pk):
    salary = get_object_or_404(Salary, pk=pk)
    try:
        salary.create_journal_entry()
        salary.is_paid = True
        salary.save(update_fields=['is_paid'])
        messages.success(request, 'تم ترحيل قيد الرواتب بنجاح')
    except Exception as e:
        messages.error(request, 'حدث خطأ أثناء الترحيل. تأكد من صحة البيانات وحاول مرة أخرى.')
        logger.exception('Posting failed for Salary %s', pk)
    return redirect('hr:salary_list')


@screen_permission_required('hr.employee', 'view')
def department_list(request):
    departments = Department.objects.filter(is_active=True)
    return render(request, 'hr/department_list.html', {'departments': departments})


@screen_permission_required('hr.employee', 'add')
def department_create(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء القسم بنجاح')
            return redirect('hr:department_list')
    else:
        form = DepartmentForm()
    return render(request, 'hr/department_form.html', {'form': form})


@screen_permission_required('hr.employee', 'view')
def department_detail(request, pk):
    department = get_object_or_404(Department, pk=pk)
    employees = Employee.objects.filter(department=department, status='active')
    return render(request, 'hr/department_detail.html', {
        'department': department,
        'employees': employees,
    })


@screen_permission_required('hr.employee', 'edit')
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل القسم بنجاح')
            return redirect('hr:department_detail', pk=pk)
    else:
        form = DepartmentForm(instance=department)
    return render(request, 'hr/department_form.html', {'form': form, 'department': department})


@require_POST
@screen_permission_required('hr.employee', 'delete')
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if Employee.objects.filter(department=department).exists():
        messages.error(request, 'لا يمكن حذف قسم يحتوي على موظفين')
    else:
        department.delete()
        messages.success(request, 'تم حذف القسم بنجاح')
    return redirect('hr:department_list')


@screen_permission_required('hr.employee', 'view')
def salary_detail(request, pk):
    salary = get_object_or_404(Salary, pk=pk)
    return render(request, 'hr/salary_detail.html', {'salary': salary})


@screen_permission_required('hr.employee', 'view')
def attendance_detail(request, pk):
    attendance = get_object_or_404(Attendance, pk=pk)
    return render(request, 'hr/attendance_detail.html', {'attendance': attendance})


@screen_permission_required('hr.employee', 'export')
def export_employees(request):
    employees = Employee.objects.filter(status='active').select_related('department')
    return export_to_excel(employees, [
        {'field': 'employee_number', 'header': 'رقم الموظف', 'width': 15},
        {'field': lambda e: f'{e.first_name} {e.last_name}', 'header': 'الاسم الكامل', 'width': 25},
        {'field': 'department', 'header': 'القسم', 'width': 20},
        {'field': 'position', 'header': 'المنصب', 'width': 20},
        {'field': 'salary', 'header': 'الراتب', 'width': 15},
        {'field': 'status', 'header': 'الحالة', 'width': 12},
    ], filename="employees")


@screen_permission_required('hr.employee', 'export')
def export_salaries(request):
    salaries = Salary.objects.select_related('employee').all()
    return export_to_excel(salaries, [
        {'field': 'employee', 'header': 'الموظف', 'width': 25},
        {'field': 'month', 'header': 'الشهر', 'width': 10},
        {'field': 'year', 'header': 'السنة', 'width': 10},
        {'field': 'basic_salary', 'header': 'الراتب الأساسي', 'width': 18},
        {'field': 'net_salary', 'header': 'الراتب الصافي', 'width': 18},
        {'field': 'is_paid', 'header': 'مدفوع', 'width': 10},
    ], filename="salaries")


@screen_permission_required('hr.employee', 'add')
def import_employees(request):
    if request.method != 'POST':
        return redirect('hr:employee_list')
    file = request.FILES.get('excel_file')
    if not file:
        messages.error(request, 'يرجى اختيار ملف Excel')
        return redirect('hr:employee_list')
    try:
        import uuid
        from datetime import date
        from decimal import Decimal
        from django.db import transaction
        rows = import_from_excel(file, [
            {'field': 'employee_number', 'header': 'رقم الموظف'},
            {'field': 'full_name', 'header': 'الاسم الكامل'},
            {'field': 'department', 'header': 'القسم'},
            {'field': 'position', 'header': 'المنصب'},
            {'field': 'salary', 'header': 'الراتب', 'type': 'decimal'},
            {'field': 'status', 'header': 'الحالة'},
            {'field': 'national_id', 'header': 'رقم الهوية'},
            {'field': 'gender', 'header': 'الجنس'},
            {'field': 'hire_date', 'header': 'تاريخ التعيين', 'type': 'date'},
        ])
        dept_lookup = {d.name: d for d in Department.objects.all()}
        created = 0
        with transaction.atomic():
            for row in rows:
                salary = row.get('salary') or Decimal('0')
                if salary < 0:
                    raise ValueError('لا يمكن أن يكون الراتب قيمة سالبة.')
                department_name = row.get('department', '')
                department = dept_lookup.get(department_name)
                full_name = row.get('full_name', '').strip()
                parts = full_name.split(' ', 1) if full_name else ['', '']
                Employee.objects.create(
                    employee_number=row.get('employee_number') or f'IMP-{uuid.uuid4().hex[:8]}',
                    first_name=parts[0] or 'غير محدد',
                    last_name=parts[1] if len(parts) > 1 else '',
                    national_id=row.get('national_id') or f'AUTO-{uuid.uuid4().hex[:12]}',
                    gender=row.get('gender') or 'male',
                    position=row.get('position') or 'غير محدد',
                    hire_date=row.get('hire_date') or date.today(),
                    department=department,
                    salary=salary,
                    status=row.get('status', 'active') or 'active',
                )
                created += 1
        messages.success(request, f'تم استيراد {created} موظف بنجاح')
    except Exception as e:
        messages.error(request, 'حدث خطأ أثناء الاستيراد. تأكد من صحة بيانات الملف وحاول مرة أخرى.')
        logger.exception('Import failed')
    return redirect('hr:employee_list')


@screen_permission_required('hr.employee', 'view')
def contract_list(request):
    contracts = Contract.objects.select_related('employee').all()
    return render(request, 'hr/contract_list.html', {'contracts': contracts})


@screen_permission_required('hr.employee', 'add')
def contract_create(request):
    if request.method == 'POST':
        form = ContractForm(request.POST)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.created_by = request.user
            contract.save()
            messages.success(request, 'تم إنشاء العقد بنجاح')
            return redirect('hr:contract_list')
    else:
        form = ContractForm()
    return render(request, 'hr/contract_form.html', {'form': form})


@screen_permission_required('hr.employee', 'view')
def contract_detail(request, pk):
    contract = get_object_or_404(Contract.objects.select_related('employee'), pk=pk)
    return render(request, 'hr/contract_detail.html', {'contract': contract})


@screen_permission_required('hr.employee', 'edit')
def contract_edit(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    if request.method == 'POST':
        form = ContractForm(request.POST, instance=contract)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل العقد بنجاح')
            return redirect('hr:contract_detail', pk=pk)
    else:
        form = ContractForm(instance=contract)
    return render(request, 'hr/contract_form.html', {'form': form, 'contract': contract})


@require_POST
@screen_permission_required('hr.employee', 'delete')
def contract_delete(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    contract.delete()
    messages.success(request, 'تم حذف العقد بنجاح')
    return redirect('hr:contract_list')


@screen_permission_required('hr.employee', 'view')
def leave_type_list(request):
    types = LeaveType.objects.filter(is_active=True)
    return render(request, 'hr/leave_type_list.html', {'leave_types': types})


@screen_permission_required('hr.employee', 'add')
def leave_type_create(request):
    if request.method == 'POST':
        form = LeaveTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء نوع الإجازة بنجاح')
            return redirect('hr:leave_type_list')
    else:
        form = LeaveTypeForm()
    return render(request, 'hr/leave_type_form.html', {'form': form})


@screen_permission_required('hr.employee', 'view')
def leave_list(request):
    leaves = LeaveRequest.objects.select_related('employee', 'leave_type', 'approved_by').all()
    status = request.GET.get('status')
    if status:
        leaves = leaves.filter(status=status)
    return render(request, 'hr/leave_list.html', {'leaves': leaves})


@screen_permission_required('hr.employee', 'add')
def leave_create(request):
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.created_by = request.user
            leave.save()
            messages.success(request, 'تم إنشاء طلب الإجازة بنجاح')
            return redirect('hr:leave_list')
    else:
        form = LeaveRequestForm()
    return render(request, 'hr/leave_form.html', {'form': form})


@screen_permission_required('hr.employee', 'view')
def leave_detail(request, pk):
    leave = get_object_or_404(LeaveRequest.objects.select_related('employee', 'leave_type', 'approved_by'), pk=pk)
    return render(request, 'hr/leave_detail.html', {'leave': leave})


@require_POST
@screen_permission_required('hr.employee', 'edit')
def leave_approve(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    leave.approve(request.user)
    messages.success(request, f'تم اعتماد إجازة {leave.employee.full_name}')
    return redirect('hr:leave_detail', pk=pk)


@require_POST
@screen_permission_required('hr.employee', 'edit')
def leave_reject(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    reason = request.POST.get('rejection_reason', '')
    leave.reject(request.user, reason)
    messages.warning(request, f'تم رفض إجازة {leave.employee.full_name}')
    return redirect('hr:leave_detail', pk=pk)
