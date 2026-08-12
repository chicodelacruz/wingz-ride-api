"""Filtering and ordering for the ride list."""

from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend

from wingz.domain.rides.expressions import bounding_box, haversine_km
from wingz.domain.rides.models import Ride

MAX_LATITUDE = 90.0
MAX_LONGITUDE = 180.0


class RideFilter(filters.FilterSet):
    """Filtering by ride status and by rider email.

    The email match is case-insensitive, which is what callers expect of an email
    address. `iexact` compiles to `UPPER(email) = UPPER(%s)` on PostgreSQL, and the
    user table carries a matching functional index on `UPPER(email)` so the lookup
    stays indexed rather than degrading into a sequential scan across the join.
    """

    status = filters.ChoiceFilter(choices=Ride.Status.choices)
    rider_email = filters.CharFilter(field_name="id_rider__email", lookup_expr="iexact")

    class Meta:
        model = Ride
        fields = ["status", "rider_email"]


class RideOrderingFilter(BaseFilterBackend):
    """Ordering by pickup time or by distance from a supplied point.

    Both orderings are expressed in SQL. That is a requirement rather than a
    preference: pagination applies LIMIT and OFFSET in the database, so an ordering
    computed in Python would page over rows the database had already chosen in a
    different order.

    Ordering by distance cannot use an index, because the distance is relative to a
    point supplied per request. Passing `radius_km` adds an indexed bounding-box
    prefilter, which is what keeps the sort viable on a large table — the exact
    distance is then computed only for rows inside the box.
    """

    ORDERING_PARAM = "ordering"
    LATITUDE_PARAM = "pickup_latitude"
    LONGITUDE_PARAM = "pickup_longitude"
    RADIUS_PARAM = "radius_km"

    ALLOWED_ORDERINGS = ("pickup_time", "-pickup_time", "distance", "-distance")

    def filter_queryset(self, request, queryset, view):
        ordering = request.query_params.get(self.ORDERING_PARAM)

        # No ordering requested: the queryset already carries the view's default, which
        # is a total ordering, so pagination stays stable.
        if not ordering:
            return queryset

        if ordering not in self.ALLOWED_ORDERINGS:
            raise ValidationError(
                {
                    self.ORDERING_PARAM: (
                        f"'{ordering}' is not a supported ordering. "
                        f"Choose one of: {', '.join(self.ALLOWED_ORDERINGS)}."
                    )
                }
            )

        descending = ordering.startswith("-")
        tiebreaker = "-id_ride" if descending else "id_ride"

        if ordering.endswith("distance"):
            return self._order_by_distance(request, queryset, descending, tiebreaker)

        return queryset.order_by(ordering, tiebreaker)

    def _order_by_distance(self, request, queryset, descending, tiebreaker):
        latitude = self._required_coordinate(request, self.LATITUDE_PARAM, MAX_LATITUDE)
        longitude = self._required_coordinate(request, self.LONGITUDE_PARAM, MAX_LONGITUDE)
        radius_km = self._optional_radius(request)

        queryset = queryset.annotate(distance_km=haversine_km(latitude, longitude))

        if radius_km is not None:
            # Two phases, doing different jobs. The bounding box is the performance
            # half: it is indexed, so it cheaply discards most of the table. The exact
            # distance is the correctness half: the box is a square, whose corners
            # reach about 1.41 times the radius, so filtering on the box alone would
            # return rides beyond the distance the caller asked for.
            queryset = queryset.filter(bounding_box(latitude, longitude, radius_km))
            queryset = queryset.filter(distance_km__lte=radius_km)

        field = "-distance_km" if descending else "distance_km"

        return queryset.order_by(field, tiebreaker)

    def _required_coordinate(self, request, param, limit):
        raw = request.query_params.get(param)

        if raw in (None, ""):
            raise ValidationError(
                {
                    param: (
                        f"'{param}' is required when ordering by distance, " f"since the distance is measured from it."
                    )
                }
            )

        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ValidationError({param: f"'{raw}' is not a valid number."})

        if not -limit <= value <= limit:
            raise ValidationError({param: f"Must be between {-limit} and {limit}."})

        return value

    def _optional_radius(self, request):
        raw = request.query_params.get(self.RADIUS_PARAM)

        if raw in (None, ""):
            return None

        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ValidationError({self.RADIUS_PARAM: f"'{raw}' is not a valid number."})

        if value <= 0:
            raise ValidationError({self.RADIUS_PARAM: "Must be greater than zero."})

        return value
