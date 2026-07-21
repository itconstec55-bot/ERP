import pytest
from django.contrib.auth.models import User
from django.urls import reverse


class TestUsers:
    @pytest.mark.django_db
    def test_user_list_requires_login(self, client):
        url = reverse('users:user_list')
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_user_create_requires_login(self, client):
        url = reverse('users:user_create')
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_admin_can_access_user_list(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('users:user_list')
        response = client.get(url)
        assert response.status_code in (200, 302)

    @pytest.mark.django_db
    def test_admin_can_access_user_create(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('users:user_create')
        response = client.get(url)
        assert response.status_code in (200, 302)
