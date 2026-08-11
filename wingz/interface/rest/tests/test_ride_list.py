"""Tests for the ride list endpoint.

The query-count tests are the reason this file exists. Everything else here is
ordinary API behaviour; the query budget is the requirement that is easy to break
accidentally and impossible to notice by reading the JSON.
"""

import pytest
from django.urls import reverse

from wingz.domain.rides.models import RideEvent
from wingz.testing import CaptureRealQueries


@pytest.fixture
def rides_with_events(make_ride, make_ride_event):
    """Three rides, each with one recent event and one older than the window."""

    def _build(count=3):
        rides = []
        for _ in range(count):
            ride = make_ride()
            make_ride_event(ride, description=RideEvent.PICKUP_DESCRIPTION, hours_ago=1)
            make_ride_event(ride, description="Ancient history", hours_ago=48)
            rides.append(ride)
        return rides

    return _build


@pytest.mark.django_db
class TestRideListQueryBudget:
    def test_list_costs_a_fixed_number_of_queries(self, admin_client, rides_with_events):
        """Four statements: authenticate, count, rides+participants, recent events.

        The specification asks for the ride list itself to cost two queries, or three
        counting the pagination COUNT. The fourth is JWT authentication resolving the
        requesting user, which happens before the view runs and is not part of
        building the list.
        """
        rides_with_events(3)

        with CaptureRealQueries() as captured:
            response = admin_client.get(reverse("ride-list"))

        assert response.status_code == 200
        assert len(captured) == 4, captured.explain()

    def test_query_count_does_not_grow_with_the_number_of_rides(self, admin_client, rides_with_events):
        """The actual guarantee: no N+1, whatever the page contains.

        Asserting a fixed number is only meaningful alongside this — a hardcoded count
        can be made to pass by tuning the fixture, but a count that stays flat as the
        result set grows tenfold cannot.
        """
        rides_with_events(2)
        with CaptureRealQueries() as few:
            admin_client.get(reverse("ride-list"))

        rides_with_events(20)
        with CaptureRealQueries() as many:
            response = admin_client.get(reverse("ride-list"))

        assert len(response.data["results"]) > 2
        assert len(many) == len(few), many.explain()

    def test_events_are_fetched_in_one_query_for_the_whole_page(self, admin_client, rides_with_events):
        """A single filtered prefetch, not one query per ride."""
        rides_with_events(5)

        with CaptureRealQueries() as captured:
            admin_client.get(reverse("ride-list"))

        event_queries = [q for q in captured.real_queries if "ride_event" in q["sql"]]

        assert len(event_queries) == 1, captured.explain()


@pytest.mark.django_db
class TestTodaysRideEvents:
    def test_only_events_from_the_last_24_hours_are_returned(self, admin_client, make_ride, make_ride_event):
        ride = make_ride()
        make_ride_event(ride, description="one hour ago", hours_ago=1)
        make_ride_event(ride, description="twenty three hours ago", hours_ago=23)
        make_ride_event(ride, description="twenty five hours ago", hours_ago=25)
        make_ride_event(ride, description="a week ago", hours_ago=24 * 7)

        response = admin_client.get(reverse("ride-list"))
        descriptions = {e["description"] for e in response.data["results"][0]["todays_ride_events"]}

        assert descriptions == {"one hour ago", "twenty three hours ago"}

    def test_a_ride_with_no_recent_events_returns_an_empty_list(self, admin_client, make_ride, make_ride_event):
        """Absence of recent events must not be null or a missing key."""
        ride = make_ride()
        make_ride_event(ride, description="long ago", hours_ago=100)

        response = admin_client.get(reverse("ride-list"))

        assert response.data["results"][0]["todays_ride_events"] == []


@pytest.mark.django_db
class TestRideListPayload:
    def test_rider_and_driver_are_nested_objects(self, admin_client, make_ride, rider, driver):
        make_ride()

        payload = admin_client.get(reverse("ride-list")).data["results"][0]

        assert payload["id_rider"]["email"] == rider.email
        assert payload["id_driver"]["email"] == driver.email
        assert payload["id_rider"]["id_user"] == rider.id_user

    def test_participant_credentials_are_not_exposed(self, admin_client, make_ride):
        make_ride()

        payload = admin_client.get(reverse("ride-list")).data["results"][0]

        for leaked in ("password", "is_superuser", "is_staff", "last_login", "user_permissions"):
            assert leaked not in payload["id_rider"]
            assert leaked not in payload["id_driver"]


@pytest.mark.django_db
class TestRideListPermissions:
    def test_anonymous_requests_are_rejected(self, api_client, make_ride):
        make_ride()

        response = api_client.get(reverse("ride-list"))

        assert response.status_code == 401

    @pytest.mark.parametrize("role", ["rider", "driver"])
    def test_non_admin_roles_are_rejected(self, authenticate, make_user, make_ride, role):
        make_ride()
        response = authenticate(make_user(role=role)).get(reverse("ride-list"))

        assert response.status_code == 403

    def test_admin_role_is_allowed(self, admin_client, make_ride):
        make_ride()

        assert admin_client.get(reverse("ride-list")).status_code == 200
