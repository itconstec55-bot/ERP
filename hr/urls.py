from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    path('create/', views.employee_create, name='employee_create'),
    path('<uuid:pk>/', views.employee_detail, name='employee_detail'),
    path('<uuid:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/create/', views.attendance_create, name='attendance_create'),
    path('salaries/', views.salary_list, name='salary_list'),
    path('salaries/create/', views.salary_create, name='salary_create'),
    path('salaries/<uuid:pk>/post/', views.salary_post, name='salary_post'),
    path('departments/', views.department_list, name='department_list'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<uuid:pk>/', views.department_detail, name='department_detail'),
    path('departments/<uuid:pk>/edit/', views.department_edit, name='department_edit'),
    path('departments/<uuid:pk>/delete/', views.department_delete, name='department_delete'),
    path('attendance/<uuid:pk>/', views.attendance_detail, name='attendance_detail'),
    path('salaries/<uuid:pk>/', views.salary_detail, name='salary_detail'),
    path('export/employees/', views.export_employees, name='export_employees'),
    path('export/salaries/', views.export_salaries, name='export_salaries'),
    path('import/employees/', views.import_employees, name='import_employees'),
    path('contracts/', views.contract_list, name='contract_list'),
    path('contracts/create/', views.contract_create, name='contract_create'),
    path('contracts/<uuid:pk>/', views.contract_detail, name='contract_detail'),
    path('contracts/<uuid:pk>/edit/', views.contract_edit, name='contract_edit'),
    path('contracts/<uuid:pk>/delete/', views.contract_delete, name='contract_delete'),
    path('leave-types/', views.leave_type_list, name='leave_type_list'),
    path('leave-types/create/', views.leave_type_create, name='leave_type_create'),
    path('leaves/', views.leave_list, name='leave_list'),
    path('leaves/create/', views.leave_create, name='leave_create'),
    path('leaves/<uuid:pk>/', views.leave_detail, name='leave_detail'),
    path('leaves/<uuid:pk>/approve/', views.leave_approve, name='leave_approve'),
    path('leaves/<uuid:pk>/reject/', views.leave_reject, name='leave_reject'),
]
