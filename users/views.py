import io
import base64
import pyotp
import qrcode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from common.permissions import screen_permission_required
from access_control.resolver import resolve
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib import messages
from django import forms
from .models import UserProfile


class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='تأكيد كلمة المرور', widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('كلمتا المرور غير متطابقتين')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class CustomUserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


@screen_permission_required('system.users', 'view')
def user_list(request):
    users = User.objects.all()
    return render(request, 'users/user_list.html', {'users': users})


@screen_permission_required('system.users', 'add')
def user_create(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'تم إنشاء المستخدم "{user.username}" بنجاح')
            return redirect('users:user_list')
    else:
        form = CustomUserCreationForm()

    return render(request, 'users/user_form.html', {'form': form, 'title': 'إنشاء مستخدم جديد'})


@login_required
def user_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.user != user_obj and not resolve(request.user).can('system.users', 'edit'):
        messages.error(request, 'ليس لديك صلاحية لتعديل هذا المستخدم')
        return redirect('users:user_list')

    if request.method == 'POST':
        form = CustomUserEditForm(request.POST, instance=user_obj)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'تم تحديث المستخدم "{user.username}" بنجاح')
            return redirect('users:user_list')
    else:
        form = CustomUserEditForm(instance=user_obj)

    return render(request, 'users/user_form.html', {
        'form': form,
        'title': f'تعديل المستخدم: {user_obj.username}', 'edit_user': user_obj,
    })


@screen_permission_required('system.users', 'delete')
@require_POST
def user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if user_obj == request.user:
        messages.error(request, 'لا يمكنك حذف حسابك الخاص')
        return redirect('users:user_list')

    username = user_obj.username
    user_obj.delete()
    messages.success(request, f'تم حذف المستخدم "{username}" بنجاح')
    return redirect('users:user_list')


@login_required
def change_password(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.user != user_obj and not resolve(request.user).can('system.users', 'edit'):
        messages.error(request, 'ليس لديك صلاحية لتغيير كلمة المرور')
        return redirect('users:user_list')

    if request.method == 'POST':
        password = request.POST.get('password')
        if password and len(password) >= 6:
            user_obj.set_password(password)
            user_obj.save()
            messages.success(request, f'تم تغيير كلمة مرور "{user_obj.username}" بنجاح')
            return redirect('users:user_list')
        else:
            messages.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')

    return render(request, 'users/change_password.html', {'edit_user': user_obj})


# ── Two-Factor Authentication Views ──────────────────────────────────────

@login_required
def two_factor_setup(request):
    """إعداد المصادقة الثنائية — توليد QR code."""
    profile = UserProfile.get_or_create_for_user(request.user)

    if profile.is_2fa_enabled:
        messages.info(request, 'المصادقة الثنائية مفعلة بالفعل.')
        return redirect('users:two_factor_status')

    if request.method == 'POST':
        code = request.POST.get('totp_code', '').strip()
        secret = request.POST.get('secret', '').strip()

        if not secret:
            secret = pyotp.random_base32()
            profile.totp_secret = secret
            profile.save(update_fields=['totp_secret'])

        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            profile.totp_secret = secret
            profile.is_2fa_enabled = True
            profile.save(update_fields=['totp_secret', 'is_2fa_enabled'])
            messages.success(request, 'تم تفعيل المصادقة الثنائية بنجاح.')
            return redirect('users:two_factor_status')
        else:
            messages.error(request, 'الرمز غير صحيح. تأكد من إدخال الرمز من تطبيق المصادقة.')

    if not profile.totp_secret:
        profile.totp_secret = pyotp.random_base32()
        profile.save(update_fields=['totp_secret'])

    totp = pyotp.TOTP(profile.totp_secret)
    uri = totp.provisioning_uri(
        name=request.user.username,
        issuer_name='نظام المحاسبة'
    )

    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'users/two_factor_setup.html', {
        'secret': profile.totp_secret,
        'qr_code': qr_base64,
    })


@login_required
def two_factor_verify(request):
    """التحقق من رمز المصادقة الثنائية."""
    profile = UserProfile.get_or_create_for_user(request.user)

    if not profile.is_2fa_enabled:
        return redirect('users:two_factor_setup')

    if request.method == 'POST':
        code = request.POST.get('totp_code', '').strip()
        if profile.verify_totp(code):
            request.session['2fa_verified'] = True
            request.session['2fa_verified_user'] = request.user.pk
            messages.success(request, 'تم التحقق بنجاح.')
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        else:
            messages.error(request, 'الرمز غير صحيح. حاول مرة أخرى.')

    return render(request, 'users/two_factor_verify.html')


@login_required
def two_factor_status(request):
    """عرض حالة المصادقة الثنائية."""
    profile = UserProfile.get_or_create_for_user(request.user)
    return render(request, 'users/two_factor_status.html', {'profile': profile})


@login_required
@require_POST
def two_factor_disable(request):
    """تعطيل المصادقة الثنائية."""
    profile = UserProfile.get_or_create_for_user(request.user)
    password = request.POST.get('password', '')
    if not request.user.check_password(password):
        messages.error(request, 'كلمة المرور غير صحيحة.')
        return redirect('users:two_factor_status')

    profile.is_2fa_enabled = False
    profile.save(update_fields=['is_2fa_enabled'])
    request.session['2fa_verified'] = False
    messages.success(request, 'تم تعطيل المصادقة الثنائية.')
    return redirect('users:two_factor_status')


# ── Session Management Views ──────────────────────────────────────────────

@login_required
def session_list(request):
    """عرض جميع الجلسات النشطة للمستخدم."""
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    sessions = Session.objects.filter(
        expire_date__gte=timezone.now()
    ).order_by('-expire_date')

    user_sessions = []
    current_session_key = request.session.session_key
    for session in sessions:
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(request.user.pk):
            user_sessions.append({
                'session_key': session.session_key,
                'expire_date': session.expire_date,
                'is_current': session.session_key == current_session_key,
                'ip': data.get('ip_address', 'غير معروف'),
                'user_agent': data.get('user_agent', 'غير معروف'),
            })

    return render(request, 'users/session_list.html', {
        'sessions': user_sessions,
    })


@login_required
@require_POST
def session_revoke(request, session_key):
    """حذف جلسة محددة."""
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    if session_key == request.session.session_key:
        messages.error(request, 'لا يمكنك حذف جلستك الحالية.')
        return redirect('users:session_list')

    try:
        session = Session.objects.get(session_key=session_key)
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(request.user.pk):
            session.delete()
            messages.success(request, 'تم حذف الجلسة بنجاح.')
        else:
            messages.error(request, 'هذه الجلسة لا تنتمي لك.')
    except Session.DoesNotExist:
        messages.error(request, 'الجلسة غير موجودة.')

    return redirect('users:session_list')


@login_required
@require_POST
def session_revoke_all(request):
    """حذف جميع الجلسات ما عدا الحالية."""
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    current_key = request.session.session_key
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    deleted = 0
    for session in sessions:
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(request.user.pk) and session.session_key != current_key:
            session.delete()
            deleted += 1

    messages.success(request, f'تم حذف {deleted} جلسة.')
    return redirect('users:session_list')
