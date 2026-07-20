import pytest
from django.contrib.auth.models import User


@pytest.fixture(autouse=True)
def enable_db_access(db):
    """تمكين الوصول إلى قاعدة البيانات لكل الاختبارات"""
    pass


@pytest.fixture
def admin_user(db):
    """مستخدم مسؤول للاختبارات"""
    return User.objects.create_superuser('admin', 'admin@test.com', 'admin123', is_staff=True, is_superuser=True)


@pytest.fixture
def regular_user(db):
    """مستخدم عادي للاختبارات"""
    return User.objects.create_user('user', 'user@test.com', 'user123')


@pytest.fixture
def api_client():
    """عميل API مع مصادقة"""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def auth_api_client(api_client, admin_user):
    """عميل API مع مصادقة المسؤول"""
    from rest_framework.authtoken.models import Token

    token, _ = Token.objects.get_or_create(user=admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return api_client
