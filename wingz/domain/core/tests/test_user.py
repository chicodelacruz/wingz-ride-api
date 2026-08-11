"""Tests for the custom user model.

Scope is deliberately narrow: the parts that differ from stock Django (email as the
identifier, and `role` driving API authorisation) are worth testing; Django's own
password and permission machinery is not.
"""

import pytest
from django.db import IntegrityError

from wingz.domain.core.models import User


@pytest.mark.django_db
class TestUserManager:
    def test_create_user_hashes_the_password(self, make_user):
        user = make_user(password="plaintext")

        assert user.password != "plaintext"
        assert user.check_password("plaintext")

    def test_create_user_requires_an_email(self):
        with pytest.raises(ValueError, match="email address"):
            User.objects.create_user(email="", password="pw")

    def test_email_is_unique(self, make_user):
        make_user(email="taken@example.com")

        with pytest.raises(IntegrityError):
            make_user(email="taken@example.com")

    def test_superuser_also_gets_the_admin_role(self):
        """A Django superuser that cannot call the API would be a confusing default.

        Authorisation here keys off `role`, not `is_superuser`, so createsuperuser has
        to grant the role explicitly or the account is useless against the API.
        """
        user = User.objects.create_superuser(
            email="root@example.com",
            password="pw",
            first_name="Root",
            last_name="User",
        )

        assert user.is_superuser
        assert user.is_staff
        assert user.role == User.Role.ADMIN
        assert user.is_admin_role


@pytest.mark.django_db
class TestUserRole:
    @pytest.mark.parametrize(
        "role,expected",
        [
            (User.Role.ADMIN, True),
            (User.Role.DRIVER, False),
            (User.Role.RIDER, False),
        ],
    )
    def test_is_admin_role_only_for_admins(self, make_user, role, expected):
        assert make_user(role=role).is_admin_role is expected

    def test_is_admin_role_is_independent_of_is_staff(self, make_user):
        """Django admin access and API access are separate questions."""
        user = make_user(role=User.Role.DRIVER, is_staff=True)

        assert user.is_staff
        assert not user.is_admin_role
