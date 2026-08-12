"""API-level validation and the user / ride-event endpoints."""

import pytest
from django.urls import reverse
from django.utils import timezone

from wingz.domain.core.models import User


def ride_payload(rider, driver, **overrides):
    payload = {
        "status": "en-route",
        "id_rider": rider.id_user,
        "id_driver": driver.id_user,
        "pickup_latitude": 14.5995,
        "pickup_longitude": 120.9842,
        "dropoff_latitude": 14.5547,
        "dropoff_longitude": 121.0244,
        "pickup_time": timezone.now().isoformat(),
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestRideCoordinateValidation:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("pickup_latitude", 999.0),
            ("pickup_longitude", -5000.0),
            ("dropoff_latitude", -91.0),
            ("dropoff_longitude", 180.1),
        ],
    )
    def test_out_of_range_coordinates_are_rejected_with_a_readable_error(
        self, admin_client, rider, driver, field, value
    ):
        """A 400 naming the offending field, not a 500 from the database constraint."""
        response = admin_client.post(reverse("ride-list"), ride_payload(rider, driver, **{field: value}), format="json")

        assert response.status_code == 400
        assert field in response.data

    def test_valid_coordinates_are_accepted(self, admin_client, rider, driver):
        response = admin_client.post(reverse("ride-list"), ride_payload(rider, driver), format="json")

        assert response.status_code == 201


@pytest.mark.django_db
class TestUserEndpoint:
    def test_admin_can_list_users(self, admin_client, rider):
        response = admin_client.get(reverse("user-list"))

        assert response.status_code == 200
        assert response.data["count"] >= 1

    def test_password_is_never_returned(self, admin_client, rider):
        response = admin_client.get(reverse("user-list"))

        for user in response.data["results"]:
            assert "password" not in user

    def test_created_user_has_a_hashed_password(self, admin_client):
        response = admin_client.post(
            reverse("user-list"),
            {
                "email": "new.driver@example.com",
                "first_name": "New",
                "last_name": "Driver",
                "role": "driver",
                "password": "a-sufficiently-long-password",
            },
            format="json",
        )

        assert response.status_code == 201
        created = User.objects.get(email="new.driver@example.com")
        assert created.password != "a-sufficiently-long-password"
        assert created.check_password("a-sufficiently-long-password")

    def test_weak_passwords_are_rejected(self, admin_client):
        response = admin_client.post(
            reverse("user-list"),
            {
                "email": "weak@example.com",
                "first_name": "Weak",
                "last_name": "Password",
                "role": "rider",
                "password": "1234",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "password" in response.data

    def test_non_admin_cannot_list_users(self, authenticate, make_user):
        response = authenticate(make_user(role=User.Role.RIDER)).get(reverse("user-list"))

        assert response.status_code == 403


@pytest.mark.django_db
class TestRideEventEndpoint:
    def test_admin_can_create_an_event(self, admin_client, make_ride):
        ride = make_ride()

        response = admin_client.post(
            reverse("rideevent-list"),
            {"id_ride": ride.id_ride, "description": "Status changed to pickup"},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["id_ride"] == ride.id_ride

    def test_events_are_listed_newest_first(self, admin_client, make_ride, make_ride_event):
        ride = make_ride()
        make_ride_event(ride, description="older", hours_ago=5)
        make_ride_event(ride, description="newer", hours_ago=1)

        response = admin_client.get(reverse("rideevent-list"))
        descriptions = [event["description"] for event in response.data["results"]]

        assert descriptions.index("newer") < descriptions.index("older")

    def test_non_admin_cannot_list_events(self, authenticate, make_user, make_ride):
        make_ride()
        response = authenticate(make_user(role=User.Role.DRIVER)).get(reverse("rideevent-list"))

        assert response.status_code == 403

    def test_full_history_for_one_ride_is_reachable(self, admin_client, make_ride, make_ride_event):
        """The ride list carries only 24 hours of events; everything else lives here.

        Without this the older history would be unreachable through the API, which
        would make the ride list's 24-hour window a loss of data rather than a
        deliberately bounded view of it.
        """
        ride = make_ride()
        other_ride = make_ride()
        make_ride_event(ride, description="recent", hours_ago=1)
        make_ride_event(ride, description="last week", hours_ago=24 * 7)
        make_ride_event(ride, description="last year", hours_ago=24 * 365)
        make_ride_event(other_ride, description="different ride", hours_ago=2)

        response = admin_client.get(reverse("rideevent-list"), {"id_ride": ride.id_ride})
        descriptions = {event["description"] for event in response.data["results"]}

        assert descriptions == {"recent", "last week", "last year"}

    def test_events_can_be_filtered_by_description(self, admin_client, make_ride, make_ride_event):
        ride = make_ride()
        make_ride_event(ride, description="Status changed to pickup", hours_ago=2)
        make_ride_event(ride, description="Route recalculated", hours_ago=1)

        response = admin_client.get(reverse("rideevent-list"), {"description": "Status changed to pickup"})

        assert response.data["count"] == 1
