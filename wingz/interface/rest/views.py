from datetime import timedelta

from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import viewsets

from wingz.domain.core.models import User
from wingz.domain.rides.models import Ride, RideEvent
from wingz.interface.rest.serializers import (
    RideEventSerializer,
    RideReadSerializer,
    RideWriteSerializer,
    UserSerializer,
)

# The window of ride events exposed as `todays_ride_events`.
TODAYS_EVENTS_WINDOW = timedelta(hours=24)


class RideViewSet(viewsets.ModelViewSet):
    """CRUD for rides.

    The list response is the performance-sensitive part of this API. It returns each
    ride with its rider, its driver, and its events from the last 24 hours, in a fixed
    number of queries regardless of page size:

    1. COUNT, for pagination
    2. the page of rides, with rider and driver joined in via select_related
    3. the recent events for those rides, via a single filtered prefetch

    That is three statements, or two ignoring the pagination count. Adding rides to a
    page does not add queries.
    """

    serializer_class = RideReadSerializer

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RideWriteSerializer
        return RideReadSerializer

    def get_queryset(self):
        queryset = Ride.objects.all()

        if self.action in ("list", "retrieve"):
            queryset = queryset.select_related("id_rider", "id_driver").prefetch_related(self._todays_events_prefetch())

        # An explicit, total ordering. Without one PostgreSQL may return rows in any
        # order, which makes paginated results non-deterministic — a row can appear on
        # two pages or none. The id tiebreaker matters because pickup_time is not
        # unique.
        return queryset.order_by("-pickup_time", "-id_ride")

    @staticmethod
    def _todays_events_prefetch():
        """Prefetch only the last 24 hours of events, as a separate list attribute.

        The cutoff is computed per request rather than at import time, which would
        freeze it at the moment the process started.

        `to_attr` is what keeps this within the query budget: the events land on
        `ride.todays_ride_events` as an ordinary list, so the serializer reads an
        attribute instead of evaluating a queryset. Without it the events would be
        cached against the default related manager and filtering them in the
        serializer would re-query per ride.
        """
        cutoff = timezone.now() - TODAYS_EVENTS_WINDOW
        recent_events = RideEvent.objects.filter(created_at__gte=cutoff).order_by("-created_at")

        return Prefetch("ride_events", queryset=recent_events, to_attr="todays_ride_events")


class UserViewSet(viewsets.ModelViewSet):
    """CRUD for users.

    Ordering is explicit for the same reason the ride list orders explicitly: without
    it, pagination over an unordered queryset is not stable.
    """

    serializer_class = UserSerializer
    queryset = User.objects.all().order_by("id_user")


class RideEventViewSet(viewsets.ModelViewSet):
    """CRUD for ride events.

    The list is ordered newest first, which is the useful default for an event log,
    with the primary key as a tiebreaker since events recorded in the same instant
    would otherwise have no defined order.
    """

    serializer_class = RideEventSerializer
    queryset = RideEvent.objects.select_related("id_ride").order_by("-created_at", "-id_ride_event")
