"""Tests for the trips-over-one-hour report.

Raw SQL gets none of the ORM's guarantees, so the edge cases are covered explicitly:
the boundary at exactly one hour, trips that never completed, duplicated events, and
the grouping and name formatting the specification's sample output implies.
"""

import datetime

import pytest

from wingz.domain.rides.models import RideEvent
from wingz.domain.rides.reports import TRIPS_OVER_ONE_HOUR_SQL, trips_over_one_hour

UTC = datetime.timezone.utc


def at(year, month, day, hour=8, minute=0):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=UTC)


@pytest.fixture
def trip(make_ride, make_user):
    """Create a ride with a pickup and (optionally) a dropoff event."""

    def _trip(picked_up_at, minutes=None, driver=None, status="en-route"):
        ride = make_ride(
            status=status,
            pickup_time=picked_up_at,
            **({"id_driver": driver} if driver else {}),
        )
        RideEvent.objects.create(
            id_ride=ride,
            description=RideEvent.PICKUP_DESCRIPTION,
            created_at=picked_up_at,
        )
        if minutes is not None:
            RideEvent.objects.create(
                id_ride=ride,
                description=RideEvent.DROPOFF_DESCRIPTION,
                created_at=picked_up_at + datetime.timedelta(minutes=minutes),
            )
        return ride

    return _trip


@pytest.mark.django_db
class TestTripDurationThreshold:
    def test_counts_only_trips_longer_than_an_hour(self, trip):
        trip(at(2026, 3, 1), minutes=90)
        trip(at(2026, 3, 2), minutes=61)
        trip(at(2026, 3, 3), minutes=30)

        rows = trips_over_one_hour()

        assert len(rows) == 1
        assert rows[0][2] == 2

    def test_exactly_one_hour_does_not_count(self, trip):
        """'More than 1 hour' is strict — a 60 minute trip is not over an hour."""
        trip(at(2026, 3, 1), minutes=60)

        assert trips_over_one_hour() == []

    def test_a_trip_without_a_dropoff_is_ignored(self, trip):
        """An in-progress ride has no duration yet, and must not be counted as zero."""
        trip(at(2026, 3, 1), minutes=None)
        trip(at(2026, 3, 2), minutes=120)

        rows = trips_over_one_hour()

        assert len(rows) == 1
        assert rows[0][2] == 1


@pytest.mark.django_db
class TestGrouping:
    def test_groups_by_month_and_driver(self, trip, make_user):
        alice = make_user(first_name="Chris", last_name="Harper", role="driver")
        bob = make_user(first_name="Howard", last_name="Yamada", role="driver")

        trip(at(2026, 1, 5), minutes=90, driver=alice)
        trip(at(2026, 1, 20), minutes=95, driver=alice)
        trip(at(2026, 1, 21), minutes=80, driver=bob)
        trip(at(2026, 2, 3), minutes=70, driver=alice)

        rows = trips_over_one_hour()

        assert rows == [
            ("2026-01", "Chris H", 2),
            ("2026-01", "Howard Y", 1),
            ("2026-02", "Chris H", 1),
        ]

    def test_month_comes_from_the_pickup(self, trip):
        """A trip crossing midnight on the last of the month belongs to the month it began."""
        trip(at(2026, 1, 31, hour=23, minute=30), minutes=90)

        rows = trips_over_one_hour()

        assert rows[0][0] == "2026-01"

    def test_driver_is_first_name_and_last_initial(self, trip, make_user):
        driver = make_user(first_name="Randy", last_name="Wilson", role="driver")
        trip(at(2026, 4, 1), minutes=75, driver=driver)

        assert trips_over_one_hour()[0][1] == "Randy W"


@pytest.mark.django_db
class TestDuplicateEvents:
    def test_earliest_pickup_and_dropoff_are_used(self, trip):
        """Events can be recorded more than once; the first of each defines the trip."""
        ride = trip(at(2026, 5, 1, hour=8), minutes=90)
        RideEvent.objects.create(
            id_ride=ride,
            description=RideEvent.PICKUP_DESCRIPTION,
            created_at=at(2026, 5, 1, hour=9),
        )
        RideEvent.objects.create(
            id_ride=ride,
            description=RideEvent.DROPOFF_DESCRIPTION,
            created_at=at(2026, 5, 1, hour=12),
        )

        rows = trips_over_one_hour()

        # 08:00 to 09:30 is the trip; the later duplicates must not stretch it, and the
        # ride must be counted once rather than once per event pair.
        assert rows == [("2026-05", rows[0][1], 1)]

    def test_unrelated_events_do_not_affect_the_result(self, trip):
        ride = trip(at(2026, 6, 1), minutes=90)
        RideEvent.objects.create(
            id_ride=ride, description="Route recalculated", created_at=at(2026, 6, 1, hour=8, minute=15)
        )

        assert trips_over_one_hour()[0][2] == 1


@pytest.mark.django_db
class TestSqlMatchesTheModel:
    def test_event_descriptions_in_the_sql_match_the_model_constants(self):
        """The SQL hardcodes the descriptions so it can be copied out and run directly.

        If the model's constants ever change, this fails rather than the report quietly
        returning nothing.
        """
        assert RideEvent.PICKUP_DESCRIPTION in TRIPS_OVER_ONE_HOUR_SQL
        assert RideEvent.DROPOFF_DESCRIPTION in TRIPS_OVER_ONE_HOUR_SQL
