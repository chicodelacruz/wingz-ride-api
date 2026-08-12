"""Database-level guarantees for ride coordinates.

The serializer rejects bad coordinates with a readable 400, but serializer validation
only protects the API. These tests cover the constraints, which hold regardless of how
the row is written — including bulk_create, a data migration, or someone in psql.
"""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from wingz.domain.rides.models import Ride


@pytest.mark.django_db
class TestCoordinateConstraints:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("pickup_latitude", 91.0),
            ("pickup_latitude", -91.0),
            ("pickup_longitude", 181.0),
            ("pickup_longitude", -181.0),
            ("dropoff_latitude", 90.5),
            ("dropoff_longitude", -180.5),
        ],
    )
    def test_out_of_range_coordinates_are_rejected_by_the_database(self, rider, driver, field, value):
        attrs = {
            "status": Ride.Status.EN_ROUTE,
            "id_rider": rider,
            "id_driver": driver,
            "pickup_latitude": 14.5995,
            "pickup_longitude": 120.9842,
            "dropoff_latitude": 14.5547,
            "dropoff_longitude": 121.0244,
            "pickup_time": timezone.now(),
            field: value,
        }

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Ride.objects.create(**attrs)

    @pytest.mark.parametrize(
        "latitude,longitude",
        [(90.0, 180.0), (-90.0, -180.0), (0.0, 0.0)],
    )
    def test_boundary_coordinates_are_accepted(self, rider, driver, latitude, longitude):
        """The extremes are valid locations, so the constraint must be inclusive."""
        ride = Ride.objects.create(
            status=Ride.Status.EN_ROUTE,
            id_rider=rider,
            id_driver=driver,
            pickup_latitude=latitude,
            pickup_longitude=longitude,
            dropoff_latitude=latitude,
            dropoff_longitude=longitude,
            pickup_time=timezone.now(),
        )

        assert ride.pk is not None
