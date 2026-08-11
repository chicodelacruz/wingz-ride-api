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

For a production install use `requirements/common.txt`, which omits the test and
linting tools.

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

**6. Run the server**

```bash
./venv/bin/python manage.py runserver 127.0.0.1:9094
```

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

Ride endpoints are documented in the section below as they are implemented.

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
- [ ] Serializers and ViewSets for CRUD
- [ ] Ride list endpoint with nested rider, driver, and events
- [ ] `todays_ride_events` via filtered prefetch, within the query budget
- [ ] Filtering by status and rider email
- [ ] Sorting by pickup time and by distance from a given point
- [ ] Reporting SQL for trips longer than one hour
