# Wingz Ride API

A RESTful API built with Django REST Framework for managing ride information — rides,
the users involved in them, and the events recorded during them.

---

## Requirements

- Python 3.12
- PostgreSQL 14 or newer (developed against 18)
- Git

No other services are needed. In particular there is no PostGIS or Docker dependency —
see [Design decisions](#design-decisions) for why the distance sort was built without
them.

---

## Setup

**1. Clone and enter the project**

```bash
git clone https://github.com/chicodelacruz/wingz-ride-api.git
cd wingz-ride-api
```

**2. Create a virtual environment and install dependencies**

```bash
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements/development.txt
```

`requirements/common.txt` holds the runtime dependencies alone; `production.txt` adds
a WSGI server. See [Running in production](#running-in-production).

**3. Configure the environment**

```bash
cp .env.example .env
```

Then edit `.env`. The value most likely to need changing is `WINGZ_DB_USER` — on a
Homebrew PostgreSQL install this is usually your macOS username rather than `postgres`.

| Variable | Purpose | Default |
| --- | --- | --- |
| `WINGZ_SECRET_KEY` | Django secret key. Signs JWTs, so must be 32+ bytes. | insecure dev value |
| `WINGZ_DB_NAME` | Database name | `wingz` |
| `WINGZ_DB_USER` | Database user | `postgres` |
| `WINGZ_DB_PASSWORD` | Database password | empty |
| `WINGZ_DB_HOST` | Database host | `localhost` |
| `WINGZ_DB_PORT` | Database port | `5432` |
| `WINGZ_SQL_LOG` | Set to `1` to echo every SQL statement to the console | `0` |

`.env` is gitignored and is never committed.

**4. Create the database and apply migrations**

```bash
createdb wingz
./venv/bin/python manage.py migrate
```

**5. Create an admin user**

Every API endpoint requires a user whose `role` is `admin`, so this step is required
before the API is usable. `createsuperuser` assigns that role automatically.

```bash
./venv/bin/python manage.py createsuperuser
```

You will be prompted for **email**, **first name**, **last name**, and a password —
there is no username field, since the specification's User table does not have one.

**6. Load demonstration data (optional)**

The API is easier to evaluate with data in it. This creates users, rides and ride
events, including trips either side of the one-hour mark so the reporting query has
something to separate, and events either side of the 24-hour mark so
`todays_ride_events` is neither always empty nor always populated.

```bash
./venv/bin/python manage.py seed_demo_data --clear --rides 60
```

It prints the demo administrator's credentials when it finishes. The random generator
is seeded, so repeated runs produce identical data. Without `--clear` it adds to
whatever is already there rather than replacing it, and says so.

> **Development only.** This command deletes ride data and creates an administrator
> whose password is committed to this repository. It refuses to run when `DEBUG` is
> `False` unless explicitly overridden, so it cannot be pointed at a deployment by
> accident.

**7. Run the server**

```bash
./venv/bin/python manage.py runserver 127.0.0.1:9094
```

Two ways to explore it by hand:

- `http://127.0.0.1:9094/admin/` — rides, events and users, with events shown inline
  on each ride
- `http://127.0.0.1:9094/api/rides/` — DRF's browsable API, usable in the browser once
  you are logged into the admin

---

## Running the tests

```bash
./venv/bin/python -m pytest
```

The full quality gate, which is what to run before committing:

```bash
./venv/bin/python -m pytest -q \
  && ./venv/bin/black --check . \
  && ./venv/bin/flake8 . \
  && ./venv/bin/python manage.py makemigrations --check --dry-run
```

Tests run against `wingz.settings.test` with `--no-migrations`, so tables are built
directly from the models. That keeps the suite fast, but it means the migration files
are not exercised by pytest — verify those separately against a clean database:

```bash
dropdb --if-exists wingz_verify && createdb wingz_verify
WINGZ_DB_NAME=wingz_verify ./venv/bin/python manage.py migrate
```

---

## Running in production

```bash
./venv/bin/python -m pip install -r requirements/production.txt

export WINGZ_SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
export WINGZ_ALLOWED_HOSTS="api.example.com"

./venv/bin/python manage.py migrate --settings=wingz.settings.production
./venv/bin/python manage.py collectstatic --noinput --settings=wingz.settings.production
./venv/bin/gunicorn wingz.wsgi:application --bind 0.0.0.0:8000
```

`wingz.settings.production` has no permissive defaults. `WINGZ_SECRET_KEY` and
`WINGZ_ALLOWED_HOSTS` raise `ImproperlyConfigured` at startup if unset — a deployment
that refuses to boot is better than one silently running on a development secret. It
also enables HSTS, SSL redirection and secure cookies, restricts the API to the JSON
renderer (the browsable API is a development convenience and needless attack surface
in production), reuses database connections, and logs to stdout.

Verify the configuration with Django's own deployment checklist:

```bash
./venv/bin/python manage.py check --deploy --settings=wingz.settings.production
```

This currently reports no issues.

### A note on the constraint migration

`0002_add_coordinate_constraints` adds two `CHECK` constraints. PostgreSQL takes an
`ACCESS EXCLUSIVE` lock and scans the whole table to validate them, which is
instantaneous on an empty table and an outage on the very large ride table this
specification describes. Against an existing large table the safe form is two steps:

```sql
ALTER TABLE ride ADD CONSTRAINT ... CHECK (...) NOT VALID;  -- instant, no scan
ALTER TABLE ride VALIDATE CONSTRAINT ...;                   -- scans under a weaker lock
```

The second statement takes `SHARE UPDATE EXCLUSIVE`, which does not block reads or
writes. The migration here uses the plain form deliberately: the table is created in
the same migration run, so there is nothing to scan and the two-step version would add
complexity for no benefit.

---

## Project structure

```
wingz/
├── domain/                 business logic and models
│   ├── core/               User
│   └── rides/              Ride, RideEvent
├── interface/              the REST layer
│   └── rest/               serializers, viewsets, filters, permissions, pagination
├── settings/               base / development / test
└── testing.py              shared test helpers
```

Each layer contributes its own settings module (`domain/settings.py`,
`interface/settings.py`) exposing an installed-apps list, which `settings/base.py`
composes. Adding a bounded context means adding its AppConfig in one place.

Only two layers are used. A four-layer split with `infrastructure/` and
`presentation/` is the fuller version of this pattern, but for an API of this size
those directories would have been empty, and empty architecture is worse than none.

---

## API

All endpoints require a JWT belonging to a user with the `admin` role.

**Obtain a token**

```bash
curl -X POST http://127.0.0.1:9094/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your-password"}'
```

Returns `access` and `refresh` tokens. Send the access token as
`Authorization: Bearer <access>` on subsequent requests, and refresh it at
`POST /api/auth/token/refresh/`.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/auth/token/` | Obtain an access/refresh token pair |
| `POST` | `/api/auth/token/refresh/` | Exchange a refresh token for a new access token |
| `GET` | `/api/rides/` | Paginated ride list, with nested rider, driver and recent events |
| `POST` | `/api/rides/` | Create a ride |
| `GET` | `/api/rides/{id}/` | Retrieve a single ride |
| `PUT` / `PATCH` | `/api/rides/{id}/` | Update a ride |
| `DELETE` | `/api/rides/{id}/` | Delete a ride |
| `GET` `POST` | `/api/ride-events/` | List (newest first) and create ride events |
| `GET` `PUT` `PATCH` `DELETE` | `/api/ride-events/{id}/` | Retrieve, update, delete a ride event |
| `GET` `POST` | `/api/users/` | List and create users |
| `GET` `PUT` `PATCH` `DELETE` | `/api/users/{id}/` | Retrieve, update, delete a user |

### Ride list

```bash
curl http://127.0.0.1:9094/api/rides/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Each ride carries its rider and driver as nested objects and a `todays_ride_events`
list holding only the events from the last 24 hours:

```json
{
  "count": 120,
  "next": "http://127.0.0.1:9094/api/rides/?page=2",
  "previous": null,
  "results": [
    {
      "id_ride": 41,
      "status": "en-route",
      "id_rider": {
        "id_user": 7,
        "role": "rider",
        "first_name": "Ada",
        "last_name": "Reyes",
        "email": "ada@example.com",
        "phone_number": "+63..."
      },
      "id_driver": { "id_user": 9, "role": "driver", "...": "..." },
      "pickup_latitude": 14.5995,
      "pickup_longitude": 120.9842,
      "dropoff_latitude": 14.5547,
      "dropoff_longitude": 121.0244,
      "pickup_time": "2026-08-12T09:15:00Z",
      "todays_ride_events": [
        {
          "id_ride_event": 88,
          "id_ride": 41,
          "description": "Status changed to pickup",
          "created_at": "2026-08-12T09:20:11Z"
        }
      ]
    }
  ]
}
```

Page size defaults to 25 and can be set per request with `?page_size=`, capped at 100.

### Filtering and ordering

| Parameter | Values | Notes |
| --- | --- | --- |
| `status` | `en-route`, `pickup`, `dropoff` | |
| `rider_email` | an email address | case-insensitive |
| `ordering` | `pickup_time`, `-pickup_time`, `distance`, `-distance` | default is `-pickup_time` |
| `pickup_latitude` | −90 to 90 | required when ordering by distance |
| `pickup_longitude` | −180 to 180 | required when ordering by distance |
| `radius_km` | any positive number | optional; restricts results and makes the distance sort indexed |

```bash
# rides currently at pickup, for one rider
curl "…/api/rides/?status=pickup&rider_email=ada@example.com" -H "Authorization: Bearer $T"

# nearest first to a point, within 5 km
curl "…/api/rides/?ordering=distance&pickup_latitude=14.5995&pickup_longitude=120.9842&radius_km=5" \
  -H "Authorization: Bearer $T"
```

When ordering by distance, each ride gains a `distance_km` field. It is omitted
otherwise, since without a point to measure from there is no distance to report.

Unsupported values are rejected with a `400` naming the parameter, rather than being
silently ignored — an ordering that quietly does nothing is worse than one that
complains.

---

## Design decisions

**The User model is custom, and email is the identifier.**
The specification's User table has `id_user`, `role`, `first_name`, `last_name`,
`email`, and `phone_number` — no username. Django's stock `AbstractUser` insists on a
username, so `User` is built on `AbstractBaseUser` + `PermissionsMixin` with `email` as
`USERNAME_FIELD`. `password`, `is_active`, `is_staff`, and `date_joined` are added
beyond the specification because Django's auth machinery and admin require them.

**Column names follow the specification exactly.**
Django names foreign key columns by appending `_id`, which would have produced
`id_rider_id` and `id_driver_id`. Each foreign key therefore declares an explicit
`db_column`. The tables are likewise named `ride`, `ride_event`, and `user` via
`db_table`. Note that `user` is a reserved word in PostgreSQL; Django quotes all
identifiers so this works transparently, but raw SQL against this schema must write
`"user"` in quotes.

**Authorisation keys off `role`, not `is_staff`.**
Whether someone may open the Django admin and whether they may call the API are
different questions. `IsAdminRole` checks `user.role == 'admin'` and is registered as
the project-wide `DEFAULT_PERMISSION_CLASSES`, so endpoints are admin-only unless they
deliberately opt out — a new endpoint cannot ship unprotected by omission.
`createsuperuser` grants the admin role too, otherwise a superuser would be unable to
use the API it administers.

**JWT needs to be told about the primary key.**
`djangorestframework-simplejwt` assumes a primary key named `id`. Because ours is
`id_user`, token creation raised `AttributeError` and the entire API was unreachable
until `SIMPLE_JWT["USER_ID_FIELD"]` was set. This is covered by a regression test that
mints a real token — the tests deliberately avoid `force_authenticate`, which bypasses
the token machinery and would have hidden the problem completely.

**`RideEvent.created_at` uses `default=timezone.now`, not `auto_now_add`.**
The reporting query needs months of historical events. `auto_now_add` ignores any value
supplied on creation, so seeded history would silently collapse onto the insert time.

**Indexes were chosen for the queries that actually run.**

| Index | Serves |
| --- | --- |
| `ride (status, pickup_time)` | the common case of filtering by status while sorting by pickup time |
| `ride (pickup_time)` | sorting by pickup time without a status filter |
| `ride (pickup_latitude, pickup_longitude)` | the bounding-box prefilter used by the distance sort |
| `ride_event (id_ride, created_at)` | the 24-hour event prefetch, keeping it off a full scan |
| `ride_event (created_at)` | time-ranged reporting queries |
| `user (UPPER(email))` | case-insensitive filtering by rider email |

That last one is worth explaining. Django compiles `iexact` to
`UPPER("email"::text) = UPPER(%s)` on PostgreSQL. A functional index on `Lower(email)`
— the more obvious choice — would never be used by the planner. The index has to match
the SQL the ORM actually emits, which was confirmed by inspecting the generated query
rather than assumed.

**The ride list costs a fixed number of queries.**
This is the requirement most easily broken by accident, so it is worth spelling out
what the endpoint actually issues. For a page of any size:

```sql
-- 1. authentication: resolve the caller from the JWT (before the view runs)
SELECT ... FROM "user" WHERE "user"."id_user" = 1;

-- 2. pagination count
SELECT COUNT(*) AS "__count" FROM "ride";

-- 3. the page of rides, with rider and driver joined in
SELECT "ride".*, "user".*, T3.*
FROM "ride"
  INNER JOIN "user" ON ("ride"."id_rider" = "user"."id_user")
  INNER JOIN "user" T3 ON ("ride"."id_driver" = T3."id_user")
ORDER BY "ride"."pickup_time" DESC, "ride"."id_ride" DESC
LIMIT 25;

-- 4. the recent events for exactly those rides, in one statement
SELECT ... FROM "ride_event"
WHERE "ride_event"."created_at" >= %s
  AND "ride_event"."id_ride" IN (...);
```

That is the two queries the specification asks for, plus the pagination `COUNT`, plus
authentication — which happens before the view is reached and is not part of building
the list.

The mechanism is `select_related` for the two participant foreign keys and a
`Prefetch(..., to_attr="todays_ride_events")` for the events. `to_attr` is doing the
important work: it attaches the filtered events to each ride as an ordinary list, so
the serializer performs an attribute access. The natural-looking alternative — a
`SerializerMethodField` that filters `obj.ride_events` — produces identical JSON and
one extra query per ride.

Two tests protect this. One asserts the exact count, and one asserts the count is
unchanged when the result set grows tenfold. The second matters more: a hardcoded
number can be made to pass by adjusting a fixture, whereas a count that stays flat as
rows multiply cannot.

**Read and write use different serializers.**
Writes accept participant ids rather than nested objects, and a newly created ride has
no `todays_ride_events` attribute, because the prefetch that supplies it only runs on
list and retrieve. Reusing the read serializer for `POST` responses would raise
`AttributeError` on every successful create.

**The list has an explicit total ordering.**
PostgreSQL makes no ordering guarantee without `ORDER BY`, so paginating an unordered
queryset can show a row on two pages or skip it entirely. The ordering is
`(-pickup_time, -id_ride)`; the id tiebreaker is required because `pickup_time` is not
unique.

**Both orderings are computed by the database, never in Python.**
This is a correctness requirement before it is a performance one. Pagination applies
`LIMIT` and `OFFSET` in SQL, so an ordering applied in Python would sort rows the
database had already selected in a different order — page two would repeat or skip
rides. A test pages through a distance-ordered result set and asserts the pages do not
overlap and that distances continue to increase across the boundary.

Sorting by `pickup_time` is served by the `(status, pickup_time)` and `(pickup_time)`
indexes. Sorting by distance cannot use an index at all, because the distance is
measured from a point supplied per request — there is no fixed value to index.

**The distance sort uses Haversine in SQL, with an optional indexed prefilter.**
The great-circle distance is built from Django's ORM maths functions rather than raw
SQL, so the coordinates remain bound parameters. It was verified against an
independent Python implementation and agrees to within a nanometre.

Haversine rather than the spherical law of cosines: the latter is shorter but loses
precision at small separations, which are precisely the distances that matter when
ordering nearby rides.

Ordering by a computed expression means reading and sorting every row. Passing
`radius_km` adds a bounding-box prefilter on the indexed latitude and longitude
columns, so the expensive trigonometry only runs over rows already narrowed by an
index. Measured on 200,000 rides:

| | Plan | Rows scanned | Time |
| --- | --- | --- | --- |
| no `radius_km` | parallel sequential scan, top-N heapsort | 200,030 | 80.6 ms |
| `radius_km=5` | bitmap index scan on `ride_pickup_latlng_idx` | 788 | 1.85 ms |

`radius_km` is applied in two phases, because the box alone is not enough. The box is
a square, so its corners reach about 1.41 times the radius — filtering on it alone
returns rides beyond the distance that was asked for. So the indexed box narrows the
candidates, and an exact distance filter then trims the corners, which makes
`radius_km` mean what it says while keeping the index scan. Two tests cover this: one
places a ride diagonally so it falls inside the box but outside the circle, and one
asserts no result ever exceeds the requested radius.

The box does not wrap across the antimeridian and widens near the poles as the
longitude correction degenerates. Both are acceptable for a prefilter of this kind and
documented in the code.

**Where this stops scaling, and what would replace it.**
Without `radius_km` the sort is still a full scan, so nearest-first across the entire
table remains expensive however it is written. The production answer is PostGIS: a
`geography` column with a GiST index, ordered with the `<->` KNN operator, which turns
nearest-neighbour into an index scan with no radius restriction.

That was deliberately not adopted here. PostGIS is a heavyweight dependency for a
project whose README promises any developer can set it up without trouble, and the KNN
ordering needs hand-written SQL either way, since GeoDjango's `Distance()` compiles to
`ST_Distance` — which PostgreSQL sorts rather than index-scans. The bounding-box
approach delivers the same practical result for bounded searches on a stock PostgreSQL
install. If nearest-first over the whole table became a real requirement, PostGIS is
the point at which the dependency would start paying for itself.

**Coordinates are validated in two places, on purpose.**
Field validators give the API a readable `400` naming the offending field. Database
`CheckConstraint`s enforce the same bounds unconditionally. Both are needed because
they cover different things: Django does not run field validators on `save()`, so the
validators alone would leave `bulk_create`, data migrations and psql sessions free to
store a latitude of 999 — which for a transport product is bad data that outlives the
request that created it. The constraints alone would work, but would surface as an
opaque `IntegrityError` instead of a useful error message.

**Passwords are write-only and never assigned directly.**
`UserSerializer` accepts a password on the way in, runs it through Django's configured
password validators, hashes it via the manager, and never includes it on the way out.
The separate `RideUserSerializer` used for the participants embedded in a ride exposes
only the six fields the specification lists, so account fields cannot leak through the
ride list.

**`ATOMIC_REQUESTS` is enabled, which complicates query counting.**
Each request runs in a transaction, so a failed write leaves nothing half-applied.
The side effect is that Django's `assertNumQueries` counts the `SAVEPOINT` and
`RELEASE SAVEPOINT` statements alongside real queries — a request issuing one query
captures three statements. Since the specification sets an explicit query budget for
the ride list, `wingz/testing.py` provides `CaptureRealQueries`, which excludes
transaction bookkeeping so the number asserted in a test is the same number quoted in
the requirement.

---

## Implementation status

- [x] Project skeleton, layered settings, environment configuration
- [x] `User`, `Ride`, `RideEvent` models with spec-conformant columns and indexes
- [x] JWT authentication and admin-role authorisation
- [x] Test harness, linting, query-counting helper
- [x] Coordinate validation at the API and database levels
- [x] Django admin for rides, events and users
- [x] Demonstration data command
- [x] Serializers and ViewSets for CRUD
- [x] Ride list endpoint with nested rider, driver, and events
- [x] `todays_ride_events` via filtered prefetch, within the query budget
- [x] Filtering by status and rider email
- [x] Sorting by pickup time and by distance from a given point
- [ ] Reporting SQL for trips longer than one hour
