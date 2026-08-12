from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

# WGS 84 bounds. Anything outside these is not a location on Earth.
LATITUDE_VALIDATORS = [MinValueValidator(-90.0), MaxValueValidator(90.0)]
LONGITUDE_VALIDATORS = [MinValueValidator(-180.0), MaxValueValidator(180.0)]


class Ride(models.Model):
    """A single ride from a pickup point to a dropoff point.

    Column names follow the assessment's Ride table. The foreign keys carry explicit
    `db_column` values because Django would otherwise store them as `id_rider_id` /
    `id_driver_id`.
    """

    class Status(models.TextChoices):
        EN_ROUTE = "en-route", "En route"
        PICKUP = "pickup", "Pickup"
        DROPOFF = "dropoff", "Dropoff"

    id_ride = models.AutoField(primary_key=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    id_rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_rider",
        related_name="rides_as_rider",
    )
    id_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_driver",
        related_name="rides_as_driver",
    )
    pickup_latitude = models.FloatField(validators=LATITUDE_VALIDATORS)
    pickup_longitude = models.FloatField(validators=LONGITUDE_VALIDATORS)
    dropoff_latitude = models.FloatField(validators=LATITUDE_VALIDATORS)
    dropoff_longitude = models.FloatField(validators=LONGITUDE_VALIDATORS)
    pickup_time = models.DateTimeField()

    class Meta:
        db_table = "ride"
        constraints = [
            # The field validators above give the API a readable 400 response, but they
            # only run through forms and serializers — Model.save() does not call them.
            # These constraints make the guarantee unconditional: no code path, including
            # bulk_create, raw ORM writes or a psql session, can store a coordinate that
            # is not a point on Earth.
            models.CheckConstraint(
                condition=models.Q(pickup_latitude__gte=-90.0, pickup_latitude__lte=90.0)
                & models.Q(pickup_longitude__gte=-180.0, pickup_longitude__lte=180.0),
                name="ride_pickup_coordinates_within_earth",
            ),
            models.CheckConstraint(
                condition=models.Q(dropoff_latitude__gte=-90.0, dropoff_latitude__lte=90.0)
                & models.Q(dropoff_longitude__gte=-180.0, dropoff_longitude__lte=180.0),
                name="ride_dropoff_coordinates_within_earth",
            ),
        ]
        indexes = [
            # Sorting by pickup_time is one of the two supported orderings, and the
            # common case is a status filter combined with that sort — so the composite
            # index leads with status and lets the index satisfy the ordering too.
            models.Index(fields=["status", "pickup_time"], name="ride_status_pickup_idx"),
            models.Index(fields=["pickup_time"], name="ride_pickup_time_idx"),
            # Supports the bounding-box prefilter used by the distance sort.
            models.Index(
                fields=["pickup_latitude", "pickup_longitude"],
                name="ride_pickup_latlng_idx",
            ),
        ]

    def __str__(self):
        return f"Ride {self.id_ride} ({self.status})"


class RideEvent(models.Model):
    """A status change or other notable moment during a ride.

    Expected to be the largest table in the system, so every access path that the API
    uses is indexed.
    """

    PICKUP_DESCRIPTION = "Status changed to pickup"
    DROPOFF_DESCRIPTION = "Status changed to dropoff"

    id_ride_event = models.AutoField(primary_key=True)
    id_ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        db_column="id_ride",
        related_name="ride_events",
    )
    description = models.CharField(max_length=255)
    # `default` rather than `auto_now_add`: events are also backfilled and seeded with
    # historical timestamps, which auto_now_add would silently overwrite.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "ride_event"
        indexes = [
            # The ride list prefetches only the last 24 hours of events per ride. This
            # index is what keeps that second query from scanning the whole table.
            models.Index(fields=["id_ride", "created_at"], name="rideevent_ride_created_idx"),
            models.Index(fields=["created_at"], name="rideevent_created_idx"),
        ]

    def __str__(self):
        return f"{self.description} @ {self.created_at:%Y-%m-%d %H:%M}"
