"""Filtering and ordering on the ride list."""

import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from wingz.domain.rides.models import Ride
from wingz.testing import CaptureRealQueries

# Manila, used as the reference point for every distance assertion here.
ORIGIN = {"pickup_latitude": 14.5995, "pickup_longitude": 120.9842}

RIDES_URL = reverse("ride-list")


@pytest.mark.django_db
class TestStatusFilter:
    def test_filters_by_status(self, admin_client, make_ride):
        make_ride(status=Ride.Status.EN_ROUTE)
        make_ride(status=Ride.Status.PICKUP)
        make_ride(status=Ride.Status.PICKUP)

        response = admin_client.get(RIDES_URL, {"status": "pickup"})

        assert response.data["count"] == 2
        assert {r["status"] for r in response.data["results"]} == {"pickup"}

    def test_unknown_status_is_rejected(self, admin_client, make_ride):
        make_ride()

        response = admin_client.get(RIDES_URL, {"status": "teleporting"})

        assert response.status_code == 400
        assert "status" in response.data


@pytest.mark.django_db
class TestRiderEmailFilter:
    def test_filters_by_rider_email(self, admin_client, make_ride, make_user):
        wanted = make_user(email="wanted@example.com")
        make_ride(id_rider=wanted)
        make_ride()

        response = admin_client.get(RIDES_URL, {"rider_email": "wanted@example.com"})

        assert response.data["count"] == 1
        assert response.data["results"][0]["id_rider"]["email"] == "wanted@example.com"

    def test_email_match_is_case_insensitive(self, admin_client, make_ride, make_user):
        """Addresses are routinely typed with different casing."""
        wanted = make_user(email="mixed.case@example.com")
        make_ride(id_rider=wanted)

        response = admin_client.get(RIDES_URL, {"rider_email": "Mixed.Case@EXAMPLE.com"})

        assert response.data["count"] == 1

    def test_filters_on_the_rider_not_the_driver(self, admin_client, make_ride, make_user):
        """A driver's address must not match the rider filter."""
        driver = make_user(email="driver-only@example.com")
        make_ride(id_driver=driver)

        response = admin_client.get(RIDES_URL, {"rider_email": "driver-only@example.com"})

        assert response.data["count"] == 0

    def test_combined_with_status(self, admin_client, make_ride, make_user):
        rider = make_user(email="combo@example.com")
        make_ride(id_rider=rider, status=Ride.Status.PICKUP)
        make_ride(id_rider=rider, status=Ride.Status.DROPOFF)

        response = admin_client.get(RIDES_URL, {"rider_email": "combo@example.com", "status": "pickup"})

        assert response.data["count"] == 1


@pytest.mark.django_db
class TestPickupTimeOrdering:
    @pytest.fixture
    def three_rides(self, make_ride):
        now = timezone.now()
        make_ride(pickup_time=now - timedelta(days=2))
        make_ride(pickup_time=now - timedelta(days=1))
        make_ride(pickup_time=now)

    def test_ascending(self, admin_client, three_rides):
        response = admin_client.get(RIDES_URL, {"ordering": "pickup_time"})
        times = [r["pickup_time"] for r in response.data["results"]]

        assert times == sorted(times)

    def test_descending(self, admin_client, three_rides):
        response = admin_client.get(RIDES_URL, {"ordering": "-pickup_time"})
        times = [r["pickup_time"] for r in response.data["results"]]

        assert times == sorted(times, reverse=True)

    def test_unsupported_ordering_is_rejected(self, admin_client, make_ride):
        make_ride()

        response = admin_client.get(RIDES_URL, {"ordering": "pickup_latitude"})

        assert response.status_code == 400
        assert "ordering" in response.data


@pytest.mark.django_db
class TestDistanceOrdering:
    @pytest.fixture
    def spread_rides(self, make_ride):
        """Three rides at increasing distance from ORIGIN."""
        near = make_ride(pickup_latitude=14.6000, pickup_longitude=120.9850)
        mid = make_ride(pickup_latitude=14.6500, pickup_longitude=121.0300)
        far = make_ride(pickup_latitude=14.9000, pickup_longitude=121.3000)
        return near, mid, far

    def test_nearest_first(self, admin_client, spread_rides):
        near, mid, far = spread_rides

        response = admin_client.get(RIDES_URL, {"ordering": "distance", **ORIGIN})
        ids = [r["id_ride"] for r in response.data["results"]]

        assert ids == [near.id_ride, mid.id_ride, far.id_ride]

    def test_farthest_first(self, admin_client, spread_rides):
        near, mid, far = spread_rides

        response = admin_client.get(RIDES_URL, {"ordering": "-distance", **ORIGIN})
        ids = [r["id_ride"] for r in response.data["results"]]

        assert ids == [far.id_ride, mid.id_ride, near.id_ride]

    def test_distance_is_reported_and_increases(self, admin_client, spread_rides):
        response = admin_client.get(RIDES_URL, {"ordering": "distance", **ORIGIN})
        distances = [r["distance_km"] for r in response.data["results"]]

        assert all(d is not None for d in distances)
        assert distances == sorted(distances)

    def test_distance_is_absent_without_a_distance_ordering(self, admin_client, make_ride):
        """No point to measure from means no distance to report."""
        make_ride()

        response = admin_client.get(RIDES_URL)

        assert "distance_km" not in response.data["results"][0]

    def test_coordinates_are_required(self, admin_client, make_ride):
        make_ride()

        response = admin_client.get(RIDES_URL, {"ordering": "distance"})

        assert response.status_code == 400
        assert "pickup_latitude" in response.data

    def test_longitude_alone_is_not_enough(self, admin_client, make_ride):
        make_ride()

        response = admin_client.get(RIDES_URL, {"ordering": "distance", "pickup_longitude": 120.98})

        assert response.status_code == 400
        assert "pickup_latitude" in response.data

    @pytest.mark.parametrize(
        "params,bad_field",
        [
            ({"pickup_latitude": "north", "pickup_longitude": 120.98}, "pickup_latitude"),
            ({"pickup_latitude": 14.6, "pickup_longitude": "east"}, "pickup_longitude"),
            ({"pickup_latitude": 91, "pickup_longitude": 120.98}, "pickup_latitude"),
            ({"pickup_latitude": 14.6, "pickup_longitude": 181}, "pickup_longitude"),
        ],
    )
    def test_invalid_coordinates_are_rejected(self, admin_client, make_ride, params, bad_field):
        make_ride()

        response = admin_client.get(RIDES_URL, {"ordering": "distance", **params})

        assert response.status_code == 400
        assert bad_field in response.data


@pytest.mark.django_db
class TestRadiusPrefilter:
    def test_radius_excludes_distant_rides(self, admin_client, make_ride):
        near = make_ride(pickup_latitude=14.6000, pickup_longitude=120.9850)
        make_ride(pickup_latitude=15.5000, pickup_longitude=121.9000)  # ~130 km away

        response = admin_client.get(RIDES_URL, {"ordering": "distance", "radius_km": 25, **ORIGIN})
        ids = [r["id_ride"] for r in response.data["results"]]

        assert ids == [near.id_ride]

    def test_radius_keeps_everything_inside_it(self, admin_client, make_ride):
        make_ride(pickup_latitude=14.6000, pickup_longitude=120.9850)
        make_ride(pickup_latitude=14.6100, pickup_longitude=120.9900)

        response = admin_client.get(RIDES_URL, {"ordering": "distance", "radius_km": 50, **ORIGIN})

        assert response.data["count"] == 2

    def test_box_corners_are_trimmed_by_the_exact_distance(self, admin_client, make_ride):
        """The bounding box is a square, so its corners reach ~1.41x the radius.

        This ride sits diagonally: inside the box, outside the circle. The box alone
        would return it for a 10 km search despite it being roughly 13 km away, so the
        exact distance filter has to run after the indexed prefilter.
        """
        due_north = make_ride(pickup_latitude=14.6400, pickup_longitude=120.9842)
        make_ride(pickup_latitude=14.6845, pickup_longitude=121.0722)

        response = admin_client.get(RIDES_URL, {"ordering": "distance", "radius_km": 10, **ORIGIN})
        ids = [r["id_ride"] for r in response.data["results"]]

        assert ids == [due_north.id_ride]

    def test_no_result_ever_exceeds_the_requested_radius(self, admin_client, make_ride):
        """The guarantee the parameter implies, asserted directly."""
        for latitude_offset in range(-6, 7):
            for longitude_offset in range(-6, 7):
                make_ride(
                    pickup_latitude=14.5995 + latitude_offset * 0.015,
                    pickup_longitude=120.9842 + longitude_offset * 0.015,
                )

        response = admin_client.get(RIDES_URL, {"ordering": "distance", "radius_km": 8, "page_size": 100, **ORIGIN})
        distances = [r["distance_km"] for r in response.data["results"]]

        assert distances, "expected at least one ride within the radius"
        assert max(distances) <= 8.0

    @pytest.mark.parametrize("radius", ["wide", -5, 0])
    def test_invalid_radius_is_rejected(self, admin_client, make_ride, radius):
        make_ride()

        response = admin_client.get(RIDES_URL, {"ordering": "distance", "radius_km": radius, **ORIGIN})

        assert response.status_code == 400
        assert "radius_km" in response.data


@pytest.mark.django_db
class TestPaginationUnderOrdering:
    def test_distance_ordering_pages_without_overlap(self, admin_client, make_ride):
        """Ordering happens in SQL, so LIMIT/OFFSET select the right rows.

        Had the sort been applied in Python after pagination, page two would repeat
        or skip rides rather than continuing the sequence.
        """
        for offset in range(10):
            make_ride(
                pickup_latitude=14.60 + offset * 0.01,
                pickup_longitude=120.99 + offset * 0.01,
            )

        params = {"ordering": "distance", "page_size": 4, **ORIGIN}
        first = admin_client.get(RIDES_URL, params).data
        second = admin_client.get(RIDES_URL, {**params, "page": 2}).data

        first_ids = [r["id_ride"] for r in first["results"]]
        second_ids = [r["id_ride"] for r in second["results"]]

        assert len(first_ids) == 4
        assert not set(first_ids) & set(second_ids)
        assert max(r["distance_km"] for r in first["results"]) <= min(r["distance_km"] for r in second["results"])

    def test_query_budget_survives_filtering_and_ordering(self, admin_client, make_ride):
        """Filters and sorts must not reintroduce per-row queries."""
        for offset in range(8):
            make_ride(pickup_latitude=14.60 + offset * 0.01, pickup_longitude=120.99)

        with CaptureRealQueries() as captured:
            response = admin_client.get(RIDES_URL, {"ordering": "distance", "status": "en-route", **ORIGIN})

        assert response.status_code == 200
        assert len(captured) == 4, captured.explain()
