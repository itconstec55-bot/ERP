import logging

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.shortcuts import redirect, render

from .forms import NotificationTemplateForm
from .models import NotificationLog, NotificationTemplate

logger = logging.getLogger('accounting')


@login_required
def notification_dashboard(request):
    logs = NotificationLog.objects.all()[:50]
    templates = NotificationTemplate.objects.all()
    return render(request, 'notifications/dashboard.html', {'logs': logs, 'templates': templates})


@login_required
def template_list(request):
    templates = NotificationTemplate.objects.all()
    return render(request, 'notifications/template_list.html', {'templates': templates})


@login_required
def template_create(request):
    if request.method == 'POST':
        form = NotificationTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء القالب')
            return redirect('notifications:template_list')
        for field, errs in form.errors.items():
            for err in errs:
                label = form.fields[field].label if field in form.fields else field
                messages.error(request, f'{label}: {err}')
    else:
        form = NotificationTemplateForm()
    return render(request, 'notifications/template_form.html', {'form': form})


@login_required
def send_test_notification(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', 'اختبار إشعار')
        body = request.POST.get('body', 'هذا اختبار من نظام المحاسبة')
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'صيغة البريد الإلكتروني غير صحيحة')
            return redirect('notifications:dashboard')
        if not request.user.is_superuser:
            allowed_domain = getattr(django_settings, 'ALLOWED_EMAIL_DOMAIN', None)
            if allowed_domain and not email.endswith(f'@{allowed_domain}'):
                messages.error(request, 'غير مسموح بالإرسال لهذا البريد الإلكتروني')
                return redirect('notifications:dashboard')
        try:
            send_mail(subject, body, django_settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            NotificationLog.objects.create(recipient_email=email, subject=subject, body=body, success=True)
            messages.success(request, f'تم الإرسال إلى {email}')
        except Exception as e:
            NotificationLog.objects.create(
                recipient_email=email, subject=subject, body=body, success=False, error_message=str(e)
            )
            messages.error(request, 'حدث خطأ أثناء إرسال البريد الإلكتروني. تأكد من صحة الإعدادات وحاول مرة أخرى.')
            logger.exception('Failed to send test email')
        return redirect('notifications:dashboard')
    return render(request, 'notifications/send_test.html')
