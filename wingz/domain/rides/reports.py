"""Reporting queries.

Written as raw SQL rather than through the ORM. The report pivots ride events into one
row per trip and then aggregates that, which is a shape the ORM expresses awkwardly and
SQL expresses directly. Keeping it as a single readable statement also makes it
reviewable by anyone who knows SQL but not Django.

The statement lives here, in one place, so the management command, the tests and the
README all refer to the same text instead of three copies that drift apart.
"""

from django.db import connection

# Descriptions the driver app writes when a ride reaches each stage. Duplicated as
# literals in the SQL below because the query is meant to be copied out and run
# directly; RideEvent.PICKUP_DESCRIPTION / DROPOFF_DESCRIPTION are the Python source of
# truth and a test asserts the two agree.
TRIPS_OVER_ONE_HOUR_SQL = """
SELECT
    to_char(trip.picked_up_at, 'YYYY-MM')                      AS month,
    driver.first_name || ' ' || left(driver.last_name, 1)      AS driver,
    count(*)                                                   AS trip_count
FROM (
    SELECT
        ride.id_ride,
        ride.id_driver,
        min(event.created_at) FILTER (
            WHERE event.description = 'Status changed to pickup'
        ) AS picked_up_at,
        min(event.created_at) FILTER (
            WHERE event.description = 'Status changed to dropoff'
        ) AS dropped_off_at
    FROM ride
    JOIN ride_event AS event ON event.id_ride = ride.id_ride
    WHERE event.description IN (
        'Status changed to pickup',
        'Status changed to dropoff'
    )
    GROUP BY ride.id_ride, ride.id_driver
) AS trip
JOIN "user" AS driver ON driver.id_user = trip.id_driver
WHERE trip.picked_up_at IS NOT NULL
  AND trip.dropped_off_at IS NOT NULL
  AND trip.dropped_off_at - trip.picked_up_at > INTERVAL '1 hour'
GROUP BY month, driver
ORDER BY month, driver;
"""


def trips_over_one_hour():
    """Run the report and return a list of (month, driver, trip_count) tuples."""
    with connection.cursor() as cursor:
        cursor.execute(TRIPS_OVER_ONE_HOUR_SQL)
        return cursor.fetchall()
