"""Tests for JWT issuance.

These exist because the User primary key is `id_user` rather than Django's default
`id`, which simplejwt does not discover on its own. Without the USER_ID_FIELD setting
every token request raises AttributeError and the entire API is unreachable — a
failure that is invisible until something asks for a token.
"""

import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken


@pytest.mark.django_db
class TestTokenObtain:
    def test_valid_credentials_return_a_token_pair(self, api_client, admin_user):
        response = api_client.post(
            reverse("token_obtain_pair"),
            {"email": admin_user.email, "password": "test-password"},
        )

        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_token_carries_the_custom_primary_key(self, api_client, admin_user):
        """Regression guard for SIMPLE_JWT["USER_ID_FIELD"].

        simplejwt serialises the id claim as a string regardless of the field's
        Python type, so the comparison is against str() rather than the raw int.
        """
        response = api_client.post(
            reverse("token_obtain_pair"),
            {"email": admin_user.email, "password": "test-password"},
        )

        token = AccessToken(response.data["access"])

        assert token["user_id"] == str(admin_user.id_user)

    def test_wrong_password_is_rejected(self, api_client, admin_user):
        response = api_client.post(
            reverse("token_obtain_pair"),
            {"email": admin_user.email, "password": "not-the-password"},
        )

        assert response.status_code == 401

    def test_unknown_email_is_rejected(self, api_client, db):
        response = api_client.post(
            reverse("token_obtain_pair"),
            {"email": "nobody@example.com", "password": "test-password"},
        )

        assert response.status_code == 401

    def test_token_endpoint_is_reachable_without_authentication(self, api_client, db):
        """The project-wide default permission is admin-only.

        If the token endpoint ever inherited that default, obtaining a token would
        require already having one.
        """
        response = api_client.post(reverse("token_obtain_pair"), {})

        assert response.status_code != 403
