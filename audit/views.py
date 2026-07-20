from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Q, Count
from django.contrib import messages
from .models import AuditLog
from common.utils import parse_date_range


@login_required
def audit_log_list(request):
    logs = AuditLog.objects.select_related('user').all()

    user_id = request.GET.get('user')
    action = request.GET.get('action')
    model = request.GET.get('model')
    date_from, date_to = parse_date_range(request)
    search = request.GET.get('q')

    if user_id:
        logs = logs.filter(user_id=user_id)
    if action:
        logs = logs.filter(action=action)
    if model:
        logs = logs.filter(model_name__icontains=model)
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)
    if search:
        logs = logs.filter(Q(object_repr__icontains=search) | Q(model_name__icontains=search))

    total_count = logs.count()
    logs = logs[:200]

    from django.contrib.auth.models import User
    users = User.objects.all()

    action_stats = AuditLog.objects.values('action').annotate(count=Count('id')).order_by('-count')
    model_stats = AuditLog.objects.values('model_name').annotate(count=Count('id')).order_by('-count')[:10]
    user_stats = AuditLog.objects.values('user__username').annotate(count=Count('id')).order_by('-count')[:10]

    return render(request, 'audit/audit_log_list.html', {
        'logs': logs,
        'users': users,
        'action_choices': AuditLog.ACTION_CHOICES,
        'total_count': total_count,
        'action_stats': action_stats,
        'model_stats': model_stats,
        'user_stats': user_stats,
    })


@login_required
def audit_export(request):
    from common.excel_utils import export_to_excel
    logs = AuditLog.objects.select_related('user').all()

    user_id = request.GET.get('user')
    action = request.GET.get('action')
    model = request.GET.get('model')
    date_from, date_to = parse_date_range(request)

    if user_id:
        logs = logs.filter(user_id=user_id)
    if action:
        logs = logs.filter(action=action)
    if model:
        logs = logs.filter(model_name__icontains=model)
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)

    return export_to_excel(logs, [
        {'field': 'timestamp', 'header': 'التاريخ والوقت', 'width': 22},
        {'field': lambda l: l.user.username if l.user else '-', 'header': 'المستخدم', 'width': 15},
        {'field': lambda l: l.get_action_display(), 'header': 'الإجراء', 'width': 15},
        {'field': 'model_name', 'header': 'النموذج', 'width': 20},
        {'field': 'object_repr', 'header': 'وصف السجل', 'width': 30},
        {'field': 'object_id', 'header': 'المعرف', 'width': 15},
        {'field': lambda l: str(l.changes)[:100] if l.changes else '', 'header': 'التغييرات', 'width': 30},
        {'field': 'ip_address', 'header': 'IP', 'width': 15},
    ], filename="audit_log")
