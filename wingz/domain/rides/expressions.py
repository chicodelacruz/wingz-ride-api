"""Geospatial expressions for ordering rides by distance.

The distance is computed by the database rather than in Python. That is not a
micro-optimisation: ordering has to happen in SQL for LIMIT/OFFSET to select the right
rows, so sorting in Python would either break pagination or require loading every ride
into memory first.

No PostGIS dependency. See the README for the trade-off and for the migration path to
a GiST index if this ever needs to scale further.
"""

import math

from django.db.models import ExpressionWrapper, F, FloatField, Q, Value
from django.db.models.functions import ATan2, Cos, Power, Radians, Sin, Sqrt

# Mean Earth radius (IUGG). Distances are returned in kilometres.
EARTH_RADIUS_KM = 6371.0088

# Degrees of latitude per kilometre is very nearly constant; longitude narrows towards
# the poles, which the bounding box corrects for.
KM_PER_DEGREE_LATITUDE = 111.045


def _float(expression):
    """Pin an expression's output type.

    Django cannot always infer the result type of mixed arithmetic, and an unresolved
    output_field raises at query-compilation time.
    """
    return ExpressionWrapper(expression, output_field=FloatField())


def haversine_km(latitude, longitude):
    """Great-circle distance from (latitude, longitude) to each ride's pickup point.

    Haversine rather than the spherical law of cosines: the latter is shorter to write
    but loses precision at small separations, which are exactly the distances that
    matter when ordering nearby rides.
    """
    origin_latitude = Radians(Value(float(latitude), output_field=FloatField()))
    origin_longitude = Radians(Value(float(longitude), output_field=FloatField()))
    pickup_latitude = Radians(F("pickup_latitude"))
    pickup_longitude = Radians(F("pickup_longitude"))

    half_latitude_delta = _float((pickup_latitude - origin_latitude) / Value(2.0))
    half_longitude_delta = _float((pickup_longitude - origin_longitude) / Value(2.0))

    chord = _float(
        Power(Sin(half_latitude_delta), Value(2.0))
        + Cos(origin_latitude) * Cos(pickup_latitude) * Power(Sin(half_longitude_delta), Value(2.0))
    )

    central_angle = _float(Value(2.0) * ATan2(Sqrt(chord), Sqrt(_float(Value(1.0) - chord))))

    return _float(Value(EARTH_RADIUS_KM) * central_angle)


def bounding_box(latitude, longitude, radius_km):
    """A Q filter selecting rides whose pickup point lies within a square around a point.

    This is the part that makes the distance sort viable on a large table. Ordering by
    a computed distance cannot use an index, so without a prefilter every row must be
    read and sorted. Latitude and longitude are indexed, so restricting to a box first
    turns a full scan into a range scan, and the expensive trigonometry then runs over
    a small subset.

    This is a prefilter and not a precise one. The box is a square, so its corners
    reach about 1.41 times the radius: it never excludes a point inside the circle, but
    it does admit points outside it. Callers that need `radius_km` to mean an actual
    radius must follow this with an exact distance filter — see RideOrderingFilter,
    which applies both.

    Limitations, both acceptable for a filter of this kind: it does not wrap across the
    antimeridian, and it widens sharply near the poles as the longitude correction
    degenerates.
    """
    latitude = float(latitude)
    longitude = float(longitude)
    radius_km = float(radius_km)

    latitude_delta = radius_km / KM_PER_DEGREE_LATITUDE

    # cos(latitude) approaches zero at the poles, which would make the longitude span
    # explode. Clamping keeps the box finite; near the poles it simply stops narrowing.
    longitude_scale = max(math.cos(math.radians(latitude)), 0.01)
    longitude_delta = radius_km / (KM_PER_DEGREE_LATITUDE * longitude_scale)

    return Q(
        pickup_latitude__gte=latitude - latitude_delta,
        pickup_latitude__lte=latitude + latitude_delta,
        pickup_longitude__gte=longitude - longitude_delta,
        pickup_longitude__lte=longitude + longitude_delta,
    )
