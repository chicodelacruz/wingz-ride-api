"""Shared pytest fixtures.

Kept at the project root so both the domain and interface suites can use them without
importing across layers.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wingz.domain.core.models import User
from wingz.domain.rides.models import Ride, RideEvent


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    """Create a user with sensible defaults; every field stays overridable."""
    counter = {"n": 0}

    def _make_user(**kwargs):
        counter["n"] += 1
        n = counter["n"]
        kwargs.setdefault("email", f"user{n}@example.com")
        kwargs.setdefault("first_name", f"First{n}")
        kwargs.setdefault("last_name", f"Last{n}")
        kwargs.setdefault("role", User.Role.RIDER)
        kwargs.setdefault("password", "test-password")
        return User.objects.create_user(**kwargs)

    return _make_user


@pytest.fixture
def admin_user(make_user):
    return make_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def rider(make_user):
    return make_user(email="rider@example.com", role=User.Role.RIDER)


@pytest.fixture
def driver(make_user):
    return make_user(email="driver@example.com", role=User.Role.DRIVER)


@pytest.fixture
def authenticate(api_client):
    """Attach a real JWT for the given user, rather than force_authenticate.

    Going through the actual token machinery means these tests would have caught the
    USER_ID_FIELD misconfiguration that force_authenticate silently bypasses.
    """

    def _authenticate(user):
        access = RefreshToken.for_user(user).access_token
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return api_client

    return _authenticate


@pytest.fixture
def admin_client(authenticate, admin_user):
    return authenticate(admin_user)


@pytest.fixture
def make_ride(db, rider, driver):
    """Create a Ride, defaulting the participants to the shared rider/driver."""

    def _make_ride(**kwargs):
        kwargs.setdefault("status", Ride.Status.EN_ROUTE)
        kwargs.setdefault("id_rider", rider)
        kwargs.setdefault("id_driver", driver)
        kwargs.setdefault("pickup_latitude", 14.5995)
        kwargs.setdefault("pickup_longitude", 120.9842)
        kwargs.setdefault("dropoff_latitude", 14.5547)
        kwargs.setdefault("dropoff_longitude", 121.0244)
        kwargs.setdefault("pickup_time", timezone.now())
        return Ride.objects.create(**kwargs)

    return _make_ride


@pytest.fixture
def make_ride_event(db):
    """Create a RideEvent, positioned relative to now via `hours_ago`."""

    def _make_ride_event(ride, description="Status changed to pickup", hours_ago=0):
        return RideEvent.objects.create(
            id_ride=ride,
            description=description,
            created_at=timezone.now() - timedelta(hours=hours_ago),
        )

    return _make_ride_event
