import pytest
from decimal import Decimal
from datetime import date
from hr.models import Department, Employee, Attendance, Salary, Contract, LeaveType, LeaveRequest
from accounts.models import Account, AccountType


@pytest.mark.django_db
class TestDepartment:
    def test_create(self):
        dept = Department.objects.create(name='المالية', manager='أحمد')
        assert dept.pk is not None
        assert str(dept) == 'المالية'
        assert dept.is_active is True


@pytest.mark.django_db
class TestEmployee:
    def test_create(self):
        dept = Department.objects.create(name='تقنية المعلومات')
        emp = Employee.objects.create(
            employee_number='EMP-001',
            first_name='محمد',
            last_name='علي',
            national_id='1234567890',
            gender='male',
            position='مبرمج',
            hire_date=date(2025, 1, 1),
            department=dept,
            salary=Decimal('5000'),
        )
        assert emp.pk is not None
        assert emp.status == 'active'

    def test_str(self):
        emp = Employee.objects.create(
            employee_number='EMP-002',
            first_name='خالد', last_name='أحمد',
            national_id='0987654321',
            gender='male', position='محاسب',
            hire_date=date(2025, 1, 1),
        )
        assert 'خالد' in str(emp) or 'EMP-002' in str(emp)


@pytest.mark.django_db
class TestLeaveType:
    def test_create(self):
        lt = LeaveType.objects.create(name='إجازة سنوية', days_per_year=21)
        assert lt.pk is not None
        assert lt.days_per_year == 21


@pytest.mark.django_db
class TestAttendance:
    def test_create(self, admin_user):
        emp = Employee.objects.create(
            employee_number='EMP-003',
            first_name='سامي', last_name='ناصر',
            national_id='1112233445',
            gender='male', position='مهندس',
            hire_date=date(2025, 1, 1),
        )
        att = Attendance.objects.create(
            employee=emp,
            date=date(2026, 7, 20),
            check_in='08:00',
            check_out='16:00',
        )
        assert att.pk is not None
