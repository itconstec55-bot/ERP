import pytest
from django.contrib.auth.models import User

from access_control.models import Role, Screen, UserRoleAssignment, UserScreenPermission


@pytest.mark.django_db
class TestRole:
    def test_create_role(self):
        role = Role.objects.create(name='مدير النظام', code='admin')
        assert role.pk is not None
        assert str(role) == 'مدير النظام'
        assert role.is_active is True

    def test_system_role_flag(self):
        role = Role.objects.create(name='دور نظامي', code='sys_role', is_system=True)
        assert role.is_system is True


@pytest.mark.django_db
class TestScreen:
    def test_create_screen(self):
        screen = Screen.objects.create(code='sales.invoice', name='فاتورة مبيعات', module='sales')
        assert screen.pk is not None
        assert 'فاتورة مبيعات' in str(screen)


@pytest.mark.django_db
class TestScreenAccess:
    def test_default_permissions(self):
        screen = Screen.objects.create(code='test.screen', name='شاشة اختبار', module='اختبار')
        access = UserScreenPermission.objects.create(
            user=User.objects.create_user('spu', 'spu@t.com', 'x1234567'), screen=screen
        )
        assert access.can_view is False
        assert access.can_add is False
        assert access.can_delete is False

    def test_grant_permissions(self):
        screen = Screen.objects.create(code='test.screen2', name='شاشة اختبار 2', module='اختبار')
        access = UserScreenPermission.objects.create(
            user=User.objects.create_user('spu2', 'spu2@t.com', 'x1234567'),
            screen=screen,
            can_view=True,
            can_add=True,
            can_edit=True,
        )
        assert access.can_view is True
        assert access.can_add is True
        assert access.can_edit is True


@pytest.mark.django_db
class TestUserRoleAssignment:
    def test_assign_role(self):
        user = User.objects.create_user('u1', 'u1@test.com', 'pass')
        role = Role.objects.create(name='مشرف', code='supervisor')
        assignment = UserRoleAssignment.objects.create(user=user, role=role)
        assert assignment.pk is not None
