# Wingz Ride API

A REST API for managing ride information, built with Django REST Framework. It covers
rides, the people involved in them, and the events recorded while a ride happens.

---

## What you need

- Python 3.12
- PostgreSQL 14 or newer (I built this against 18)
- Git

That's all. No PostGIS and no Docker — I explain why in [Design notes](#design-notes),
under the distance sorting.

---

## Getting it running

**1. Clone it**

```bash
git clone https://github.com/chicodelacruz/wingz-ride-api.git
cd wingz-ride-api
```

**2. Make a virtualenv and install**

```bash
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements/development.txt
```

`common.txt` has just the runtime packages. `production.txt` adds a WSGI server.

**3. Set up your environment file**

```bash
cp .env.example .env
```

Then open `.env`. The one you'll probably need to change is `WINGZ_DB_USER` — with
Homebrew Postgres it's usually your Mac username, not `postgres`.

| Variable | What it's for | Default |
| --- | --- | --- |
| `WINGZ_SECRET_KEY` | Django secret key. It signs the JWTs, so keep it 32+ bytes. | insecure dev value |
| `WINGZ_DB_NAME` | Database name | `wingz` |
| `WINGZ_DB_USER` | Database user | `postgres` |
| `WINGZ_DB_PASSWORD` | Database password | empty |
| `WINGZ_DB_HOST` | Database host | `localhost` |
| `WINGZ_DB_PORT` | Database port | `5432` |
| `WINGZ_SQL_LOG` | Set to `1` to print every SQL statement | `0` |

`.env` is gitignored, so it never gets committed.

**4. Create the database and migrate**

```bash
createdb wingz
./venv/bin/python manage.py migrate
```

If either of those complains, [If something goes wrong](#if-something-goes-wrong) has
the usual causes.

**5. Make an admin user**

Every endpoint needs a user whose `role` is `admin`, so you have to do this before the
API is any use. `createsuperuser` sets that role for you.

```bash
./venv/bin/python manage.py createsuperuser
```

It'll ask for **email**, **first name**, **last name** and a password. There's no
username, because the User table in the spec doesn't have one.

**6. Load some demo data (optional)**

Much easier to look around with data in there. This creates users, rides and events,
with trip lengths on both sides of the one hour mark so the report has something to
work with, and events on both sides of the 24 hour mark so `todays_ride_events` isn't
always empty or always full.

```bash
./venv/bin/python manage.py seed_demo_data --clear --rides 60
```

It prints the demo admin login when it's done. The randomness is seeded, so you get the
same data every time you run it. Leave off `--clear` and it adds to what's already
there instead of replacing it (it'll tell you when it does).

> **Don't run this on anything real.** It deletes rides and creates an admin whose
> password is sitting in this repo. It won't run when `DEBUG` is `False` unless you
> explicitly override it.

**7. Start the server**

```bash
./venv/bin/python manage.py runserver 127.0.0.1:9094
```

Two easy ways to poke at it:

- `http://127.0.0.1:9094/admin/` — rides, events and users, with each ride's events
  listed underneath it
- `http://127.0.0.1:9094/api/rides/` — the DRF browsable API, which works in the
  browser once you're logged into the admin

---

## If something goes wrong

I've only run this on macOS with Homebrew Postgres, so here are the things most likely
to trip you up somewhere else, with what the error actually looks like.

**`FATAL: role "postgres" does not exist`**

The `WINGZ_DB_USER` in your `.env` doesn't exist in your Postgres. With Homebrew the
superuser is your own Mac username, not `postgres`, so:

```bash
WINGZ_DB_USER=$(whoami)
```

`.env.example` ships `postgres` because that's the usual name on Linux and in Docker
images. If you're on a Mac, this is the line to change.

**`FATAL: database "wingz" does not exist`**

You skipped `createdb wingz`, or your `WINGZ_DB_NAME` doesn't match what you created.

**`could not receive data from server: Connection refused`**

Postgres isn't running, or it's not on the port in your `.env`. Check with
`pg_isready`. On Homebrew: `brew services start postgresql@18`.

**`FATAL: password authentication failed`**

Your Postgres wants a password. Put it in `WINGZ_DB_PASSWORD` — it's empty by default,
which works for local trust or peer auth but not much else.

**Tests fail while creating a database**

pytest builds its own test database, so your database user needs `CREATEDB`. Either
grant it (`ALTER ROLE youruser CREATEDB;`) or use a superuser locally.

**`{"detail": "This endpoint is restricted to users with the 'admin' role."}`**

Your token belongs to a real user who isn't an admin. Every endpoint needs
`role = 'admin'`. `createsuperuser` sets that for you; `seed_demo_data` prints an admin
login you can use.

**`createsuperuser` isn't asking for a username**

It shouldn't. It asks for email, first name, last name and a password, because the User
table in the spec has no username column and email is the login field.

**You're on Windows**

Every command here uses `./venv/bin/python`, which is the Unix layout. Use
`venv\Scripts\python` instead. Everything else works the same — `psycopg[binary]` ships
prebuilt wheels, so there's nothing to compile.

---

## How the code is laid out

```
wingz/
├── domain/                 models and business logic
│   ├── core/               User
│   └── rides/              Ride, RideEvent
├── interface/              the REST layer
│   └── rest/               serializers, viewsets, filters, permissions, pagination
├── settings/               base / development / test / production
└── testing.py              shared test helpers
```

Each layer has its own settings module listing the apps it adds, and
`settings/base.py` stitches them together. Adding a new area of the domain means
registering its AppConfig in one place.

I only used two layers. The fuller version of this pattern has `infrastructure/` and
`presentation/` as well, but for an API this size those folders would have been empty,
and empty folders are worse than no structure at all.

---

## Using the API

Everything needs a JWT belonging to an admin user.

**Get a token**

```bash
curl -X POST http://127.0.0.1:9094/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your-password"}'
```

You get back `access` and `refresh`. Send the access token as
`Authorization: Bearer <access>`, and refresh it at `POST /api/auth/token/refresh/`.

| Method | Path | What it does |
| --- | --- | --- |
| `POST` | `/api/auth/token/` | Get an access and refresh token |
| `POST` | `/api/auth/token/refresh/` | Trade a refresh token for a new access token |
| `GET` | `/api/rides/` | Ride list, with rider, driver and recent events |
| `POST` | `/api/rides/` | Create a ride |
| `GET` | `/api/rides/{id}/` | One ride |
| `PUT` `PATCH` | `/api/rides/{id}/` | Update a ride |
| `DELETE` | `/api/rides/{id}/` | Delete a ride |
| `GET` `POST` | `/api/ride-events/` | Events, newest first. Filter with `?id_ride=` or `?description=` |
| `GET` `PUT` `PATCH` `DELETE` | `/api/ride-events/{id}/` | One event |
| `GET` `POST` | `/api/users/` | Users |
| `GET` `PUT` `PATCH` `DELETE` | `/api/users/{id}/` | One user |

### The ride list

```bash
curl http://127.0.0.1:9094/api/rides/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Each ride comes back with its rider and driver as nested objects, plus a
`todays_ride_events` list holding only the last 24 hours of events:

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

Only the last 24 hours of events turn up here, and that's on purpose. The spec asks for
each ride's related events, but it also says the SQL must never load the full list, on a
table it expects to grow very large. Those two can't both be true literally, so I made a
call — I go through it in [the two rules about ride events](#the-two-rules-about-ride-events).
If you want a ride's whole history it's at `/api/ride-events/?id_ride=41`.

Pages are 25 by default. Use `?page_size=` to change it, up to 100.

### Filtering and sorting

| Parameter | Values | Notes |
| --- | --- | --- |
| `status` | `en-route`, `pickup`, `dropoff` | |
| `rider_email` | an email address | not case sensitive |
| `ordering` | `pickup_time`, `-pickup_time`, `distance`, `-distance` | defaults to `-pickup_time` |
| `pickup_latitude` | −90 to 90 | needed when sorting by distance |
| `pickup_longitude` | −180 to 180 | needed when sorting by distance |
| `radius_km` | any positive number | optional, and it's what makes the distance sort use an index |

```bash
# rides at pickup, for one rider
curl "…/api/rides/?status=pickup&rider_email=ada@example.com" -H "Authorization: Bearer $T"

# closest first to a point, within 5 km
curl "…/api/rides/?ordering=distance&pickup_latitude=14.5995&pickup_longitude=120.9842&radius_km=5" \
  -H "Authorization: Bearer $T"
```

When you sort by distance each ride also gets a `distance_km` field. It's left out
otherwise, since without a point to measure from there's no distance to give you.

Bad values get a `400` that tells you which parameter was wrong. I'd rather it complain
than quietly ignore what you asked for.

---

## The report: trips over an hour

Counts finished trips that took more than an hour from pickup to dropoff, grouped by
month and driver.

```sql
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
```

You can run it without copying it anywhere:

```bash
./venv/bin/python manage.py trip_duration_report
./venv/bin/python manage.py trip_duration_report --show-sql
```

```
Month      Driver                Count of Trips > 1 hr
------------------------------------------------------
2026-04    Howard C                                  1
2026-05    Howard S                                  3
2026-06    Nora H                                    1
```

### What it's doing

The inner query turns events into one row per trip. I used `FILTER` instead of
`CASE WHEN` because it reads better and Postgres handles it in one pass.

`min()` on both sides matters. An event can get recorded more than once, and taking the
earliest of each means a trip ends when it first ended, rather than stretching out to
whatever duplicate came last.

A few things the spec leaves open, which I decided one way and wrote a test for:

- **Exactly an hour doesn't count.** "More than 1 hour" reads as strict to me, so a
  60 minute trip is out.
- **Trips with no dropoff are skipped.** A ride that hasn't finished doesn't have a
  duration yet, and counting it as zero would be wrong.
- **A trip belongs to the month it started in.** One that starts 23:30 on 31 January
  and ends in February counts as January. Splitting a single trip across two months
  seemed worse.
- **Times are UTC**, since that's the connection timezone. If you were reporting to
  people in one place you'd want to convert first, or month boundaries land in odd
  spots.
- **Driver names** are first name plus last initial, matching the sample output.

The SQL lives in `wingz/domain/rides/reports.py` so the command, the tests and this
README all use the same copy. There's a test checking the event descriptions in the SQL
still match the constants on the model, so if someone renames one it fails a test
instead of the report just going quiet.

### At scale

On 200,000 rides and 400,000 events it runs in about 280 ms, with index scans on both
tables rather than sequential ones.

That's fine for something you run now and then, and it won't stay fine forever, because
it has to read every status change ever recorded. The spec actually hints at the fix
when it mentions a real system would keep the value on the ride table. Write the
duration when the dropoff happens and this becomes a simple aggregate over `ride`.
A materialised view refreshed on a schedule would work too — a report like this doesn't
need to be accurate to the second. I did neither, because the exercise asks for it to
come from the events with the ride table left alone.

---

## Design notes

### The two rules about ride events

This is the one spot where the spec asks for two things that fight each other, so it's
worth saying what I picked.

The ride list has to "include its related RideEvents". It also has to never "load the
full list of RideEvents", on a table that's "expected to grow very large". You can't do
both literally. A ride with fifty thousand events isn't going to have all of them in a
list response.

I read the second rule as limiting the first. The ride list carries
`todays_ride_events`, the last 24 hours, and nothing more. It's capped by time rather
than by count, so the response can't keep growing as history piles up.

To make sure that's a smaller view and not lost data, you can still get everything for
a ride, one ride at a time and paginated:

```bash
curl "…/api/ride-events/?id_ride=41" -H "Authorization: Bearer $T"
```

Nothing's out of reach. Asking for a full history is just something you do on purpose,
for one ride, instead of it happening on every page of a list.

### A custom User model with email as the login

The User table in the spec has `id_user`, `role`, `first_name`, `last_name`, `email`
and `phone_number`. No username. Django's `AbstractUser` insists on one, so I built on
`AbstractBaseUser` + `PermissionsMixin` with `email` as the `USERNAME_FIELD`.

I added `password`, `is_active`, `is_staff` and `date_joined` on top of the spec, since
Django's auth and admin need them.

### Column names match the spec exactly

Django would normally name foreign key columns `id_rider_id` and `id_driver_id`, so
each FK sets `db_column` explicitly. Tables are `ride`, `ride_event` and `user` via
`db_table`.

Worth knowing: `user` is a reserved word in Postgres. Django quotes identifiers so it
works fine, but if you write raw SQL against this schema you need `"user"` in quotes.

### Permissions go by `role`, not `is_staff`

Whether someone can get into the Django admin and whether they can call the API are two
different questions. `IsAdminRole` checks `user.role == 'admin'` and it's set as the
project-wide `DEFAULT_PERMISSION_CLASSES`, so endpoints are admin-only unless they opt
out. That way a new endpoint can't end up unprotected just because someone forgot.

`createsuperuser` sets the admin role too, otherwise you'd have a superuser who can't
use the API it's supposed to administer.

### JWT needs telling about the primary key

`djangorestframework-simplejwt` assumes the primary key is called `id`. Ours is
`id_user`, so until I set `SIMPLE_JWT["USER_ID_FIELD"]` every token request blew up with
an `AttributeError` and nobody could log in at all.

There's a regression test for it that mints a real token. The auth tests deliberately
avoid `force_authenticate`, because that skips the token machinery entirely and would
have hidden this completely.

### `RideEvent.created_at` uses `default`, not `auto_now_add`

The report needs months of history. `auto_now_add` throws away whatever value you pass
in, so seeded history would all collapse onto the moment it was inserted.

### Indexes follow the queries that actually run

| Index | What it's for |
| --- | --- |
| `ride (status, pickup_time)` | filtering by status while sorting by pickup time, which is the common case |
| `ride (pickup_time)` | sorting by pickup time on its own |
| `ride (pickup_latitude, pickup_longitude)` | the bounding box in the distance sort |
| `ride_event (id_ride, created_at)` | the 24 hour prefetch, so it isn't a full scan |
| `ride_event (created_at)` | time-based reporting |
| `user (UPPER(email))` | case-insensitive filtering by rider email |

That last one is worth explaining. Django turns `iexact` into
`UPPER("email"::text) = UPPER(%s)` on Postgres. An index on `Lower(email)` — the more
obvious choice — would never get used. The index has to match the SQL the ORM actually
writes, which I checked by looking at the generated query rather than guessing.

I also dropped an index on `user (role)` that I'd added out of habit. Nothing queries
by role: the permission check loads the user by primary key. It was costing writes for
nothing.

### The ride list runs a fixed number of queries

This is the easiest requirement to break by accident, so here's what actually gets sent,
for a page of any size:

```sql
-- 1. auth: work out who's calling, from the JWT (before the view runs)
SELECT ... FROM "user" WHERE "user"."id_user" = 1;

-- 2. the pagination count
SELECT COUNT(*) AS "__count" FROM "ride";

-- 3. the page of rides, with rider and driver joined in
SELECT "ride".*, "user".*, T3.*
FROM "ride"
  INNER JOIN "user" ON ("ride"."id_rider" = "user"."id_user")
  INNER JOIN "user" T3 ON ("ride"."id_driver" = T3."id_user")
ORDER BY "ride"."pickup_time" DESC, "ride"."id_ride" DESC
LIMIT 25;

-- 4. recent events for exactly those rides, in one go
SELECT ... FROM "ride_event"
WHERE "ride_event"."created_at" >= %s
  AND "ride_event"."id_ride" IN (...);
```

That's the two queries the spec asks for, plus the `COUNT`, plus auth — which happens
before the view is even reached.

It's `select_related` for the two participants and
`Prefetch(..., to_attr="todays_ride_events")` for the events. The `to_attr` is the bit
doing the work: it hangs the filtered events off each ride as a plain list, so the
serializer just reads an attribute. The obvious alternative, a `SerializerMethodField`
filtering `obj.ride_events`, gives you identical JSON and one extra query per ride.

Two tests guard this. One checks the exact number. The other checks the number doesn't
change when the result set gets ten times bigger. The second one matters more — you can
make a hardcoded number pass by fiddling with a fixture, but you can't fake a count that
stays flat while rows multiply.

### Reading and writing use different serializers

Writes take participant IDs rather than nested objects. And a ride you've just created
has no `todays_ride_events` attribute, because the prefetch only runs on list and
retrieve. Reusing the read serializer for `POST` responses would throw `AttributeError`
on every successful create.

### The list always has a total ordering

Postgres promises nothing about row order without `ORDER BY`, so paginating an unordered
queryset can show you the same row twice or skip it. The ordering is
`(-pickup_time, -id_ride)`. The ID tiebreaker is there because `pickup_time` isn't
unique.

### Sorting happens in SQL, never in Python

This is about correctness first, speed second. Pagination applies `LIMIT` and `OFFSET`
in the database, so sorting in Python would mean paging over rows the database had
already picked in some other order — page two would repeat rides or skip them. There's
a test that pages through a distance-sorted result and checks the pages don't overlap
and the distances keep going up across the boundary.

Sorting by `pickup_time` uses the indexes above. Sorting by distance can't use an index
at all, because the point you're measuring from changes with every request.

### Distance sorting

The great-circle distance is built from Django's ORM maths functions rather than raw
SQL, so the coordinates stay bound parameters. I checked it against a separate Python
implementation and they agree to within a nanometre.

I used haversine rather than the spherical law of cosines. The latter is shorter to
write but loses accuracy over short distances, which are exactly the ones that matter
when you're sorting nearby rides.

Sorting by something the database has to calculate means reading and sorting every row.
Passing `radius_km` adds a bounding box over the indexed latitude and longitude columns
first, so the expensive trigonometry only runs on rows an index has already narrowed
down. On 200,000 rides:

| | Plan | Rows read | Time |
| --- | --- | --- | --- |
| no `radius_km` | parallel sequential scan, top-N heapsort | 200,030 | 80.6 ms |
| `radius_km=5` | bitmap index scan on `ride_pickup_latlng_idx` | 788 | 1.85 ms |

`radius_km` runs in two steps, because the box on its own isn't enough. A box is a
square, so its corners reach about 1.41 times the radius, and filtering on it alone
hands back rides further away than you asked for. So the box narrows things down using
the index, then an exact distance filter trims the corners off. Two tests cover it: one
puts a ride diagonally so it lands inside the box but outside the circle, and one checks
nothing ever comes back past the radius you gave.

The box doesn't wrap around the antimeridian, and it gets wide near the poles as the
longitude correction breaks down. Both are fine for a rough prefilter and both are noted
in the code.

### Where this stops scaling, and what I'd do instead

Without `radius_km` it's still a full scan, so nearest-first across the whole table is
expensive no matter how you write it. The real answer is PostGIS: a `geography` column
with a GiST index, sorted with the `<->` KNN operator, which turns nearest-neighbour
into an index scan with no radius needed.

I decided against it. PostGIS is a heavy dependency for a project whose README promises
you can set it up without trouble, and the KNN ordering needs hand-written SQL anyway,
because GeoDjango's `Distance()` compiles to `ST_Distance` and Postgres sorts that
rather than scanning an index for it. The bounding box gets you the same practical
result for bounded searches on plain Postgres. If searching the whole table by distance
became a real requirement, that's the point where PostGIS would start earning its keep.

### Coordinates get checked twice

Field validators give you a readable `400` naming the field that's wrong. Database
`CHECK` constraints enforce the same limits no matter what.

You need both, because they cover different things. Django doesn't run field validators
on `save()`, so validators alone would leave `bulk_create`, data migrations and anyone
in psql free to store a latitude of 999 — and bad location data outlives the request
that created it. Constraints alone would work, but you'd get an unhelpful
`IntegrityError` instead of a message telling you what went wrong.

### Passwords are write-only and never set directly

`UserSerializer` takes a password on the way in, runs it through Django's password
validators, hashes it through the manager, and never sends it back out. The separate
`RideUserSerializer` used for riders and drivers inside a ride only exposes the six
fields the spec lists, so account fields can't leak out through the ride list.

### `ATOMIC_REQUESTS` makes counting queries awkward

Every request runs in a transaction, so a failed write can't leave things half done.
The side effect is that Django's `assertNumQueries` counts the `SAVEPOINT` and
`RELEASE SAVEPOINT` statements alongside real ones — a request doing one query looks
like three.

Since the spec gives an explicit query budget, `wingz/testing.py` has
`CaptureRealQueries`, which leaves out the transaction bookkeeping. That way the number
in the test is the same number in the requirement.

---

## What went wrong along the way

Most of the design notes above read like decisions. Some of them started out as bugs.
Here's what actually bit me, since that's probably more useful than a tidy story.

**Nobody could log in, and nothing said so.** `simplejwt` assumes the primary key is
called `id`. Ours is `id_user`, so every single token request died with an
`AttributeError` and the entire API was unreachable. What makes this one worth
mentioning is how easy it was to miss: `force_authenticate` in tests skips the token
machinery completely, so a full green test suite would have told me nothing. I only
caught it because the auth tests mint real tokens. That's now the reason they do.

**I indexed the wrong function.** I'd put a functional index on `Lower(email)` for the
case-insensitive rider filter, which is the obvious choice and completely useless —
Django compiles `iexact` into `UPPER("email"::text)`. The planner would have ignored my
index forever and I'd never have known, because the query still returns the right
answer. Found it by printing the generated SQL instead of trusting my assumption about
what the ORM writes.

**The API happily accepted latitude 999.** There was no coordinate validation at all to
begin with, and `POST` with latitude 999 and longitude −5000 came back `201 Created`. It
only turned up when I went looking for holes rather than testing the happy path. Fixing
it is what led to validating in two places, since serializer validation alone still
leaves `bulk_create` and psql free to write nonsense.

**`radius_km` was quietly lying.** Asking for rides within 10 km returned rides about
13 km away. A bounding box is a square, so its corners reach roughly 1.41 times the
radius, and I'd only filtered on the box. The embarrassing part is that I had tests for
the radius and they all passed — they used points either clearly inside the box or far
outside it, so nothing ever landed in a corner. I found it running checks by hand
against real data. Now there's a test that puts a ride diagonally on purpose, and the
box is followed by an exact distance filter.

**Counting queries didn't mean what I thought.** `ATOMIC_REQUESTS` wraps each request in
a transaction, so `assertNumQueries` counts `SAVEPOINT` and `RELEASE SAVEPOINT` along
with the real ones — a request doing one query looks like three. Since the spec sets an
actual number, asserting a number that included transaction bookkeeping would have been
meaningless. Hence `CaptureRealQueries`.

**The admin looked broken but wasn't.** I seeded a demo admin with `is_staff=True` and
no permissions. Django lets that account log in and then shows it an empty admin,
because the index only lists models you have permission for. It looks exactly like a
broken install. It's a superuser now, and the seed command repairs an old account rather
than skipping it.

**GeoDjango wouldn't have helped.** I'd assumed PostGIS was the answer for the distance
sort until I looked into what GeoDjango actually generates. `Distance()` compiles to
`ST_Distance`, which Postgres sorts rather than index-scans — you need the `<->` KNN
operator for that, and that means hand-written SQL either way. So the heavy dependency
wouldn't have bought me the one thing I wanted it for. That's what tipped me towards
the bounding box.

The pattern in most of these is the same: the code looked right, the tests were green,
and the JSON was correct. What found them was checking the thing underneath — the SQL
Django emits, the query plan, the actual numbers coming back — instead of trusting that
the layer above was telling the truth.

---

## Running the tests

```bash
./venv/bin/python -m pytest
```

Everything I run before committing:

```bash
./venv/bin/python -m pytest -q \
  && ./venv/bin/black --check . \
  && ./venv/bin/flake8 . \
  && ./venv/bin/python manage.py makemigrations --check --dry-run
```

Tests use `wingz.settings.test` with `--no-migrations`, so tables get built straight
from the models. That keeps them fast, but it does mean the migration files themselves
aren't tested. Check those separately against a clean database:

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

`wingz.settings.production` has no forgiving defaults. `WINGZ_SECRET_KEY` and
`WINGZ_ALLOWED_HOSTS` raise `ImproperlyConfigured` if they're missing — I'd much rather
a deploy refuse to start than come up quietly using a development secret. It also turns
on HSTS, SSL redirect and secure cookies, drops the browsable API in favour of JSON only
(it's a dev convenience and extra surface area in production), reuses database
connections, and logs to stdout.

You can check it with Django's own deployment checklist:

```bash
./venv/bin/python manage.py check --deploy --settings=wingz.settings.production
```

It comes back clean.

### One note on the constraint migration

`0002_add_coordinate_constraints` adds two `CHECK` constraints. Postgres takes an
`ACCESS EXCLUSIVE` lock and reads the whole table to validate them, which is instant on
an empty table and an outage on the very large ride table the spec describes. Against a
big existing table you'd want two steps:

```sql
ALTER TABLE ride ADD CONSTRAINT ... CHECK (...) NOT VALID;  -- instant, no scan
ALTER TABLE ride VALIDATE CONSTRAINT ...;                   -- scans, but a weaker lock
```

The second takes `SHARE UPDATE EXCLUSIVE`, which doesn't block reads or writes. I used
the plain form here on purpose: the table gets created in the same migration run, so
there's nothing to scan and the two-step version would just be extra complexity.

---

## Known limitations

Things I know about and chose not to do, with why. If any of these matter for real
usage they're the first things I'd pick up.

**Deep pagination gets slower the further in you go.** Page numbers turn into
`LIMIT`/`OFFSET`, and `OFFSET` makes Postgres walk and throw away every row it skips.
Page 500 costs a lot more than page 1. Cursor pagination fixes that, but it needs a
stable ordering key, and the distance sort doesn't have one — it's calculated fresh from
whatever point you pass in. Supporting cursors for pickup time and page numbers for
distance would mean two pagination styles on one endpoint, which felt like a worse
trade than the spec was asking for.

**Sorting by distance with no `radius_km` reads the whole table.** There's no way round
it without a spatial index. PostGIS with a GiST index and the `<->` operator is the
proper fix, and I've written up why I didn't pull that dependency in
[design notes](#where-this-stops-scaling-and-what-id-do-instead). If you're searching
within a radius, which is the normal case for a rideshare product, the bounding box
already handles it.

**The report reads every status change ever recorded.** About 280 ms over 400,000
events, which is fine now and won't be forever. Storing the duration on the ride when
the dropoff lands, or a materialised view on a schedule, is the real answer. The spec
rules out changing the ride table, so I left it.

**No rate limiting.** Nothing was asked for and I didn't want to guess at limits, but a
public API wants throttling, and DRF's is a few lines of settings.

**No OpenAPI schema.** `drf-spectacular` would generate one and give you Swagger UI.
For an API this size the README covers it, but a schema is what you'd want if other
teams were building against this.

**`select_related` pulls every column on both users, password hash included.** It never
reaches the JSON — the serializer only exposes six fields and there's a test for that —
but it does get read into memory on every list request. `.only()` would trim it. I left
it because it saves no queries, and if someone later adds a field to the serializer and
forgets the `.only()` list, Django silently fires a query per row and you're back to the
N+1 the whole design exists to avoid. Not a trap worth leaving lying around for a
narrower row.

**The bounding box doesn't wrap the antimeridian**, and it gets very wide near the
poles as the longitude correction falls apart. Neither matters for rides in one metro
area. Both would matter for a global dataset.

**Report months are UTC.** The connection timezone is UTC, so a trip at 23:30 local
time can land in a different month than a local reader expects. Reporting for one
region, you'd convert first.

---

## Where each requirement lives

| Requirement | Where |
| --- | --- |
| Models for Ride, User, RideEvent | `wingz/domain/{core,rides}/models.py` |
| Serializers for each model | `wingz/interface/rest/serializers.py` |
| ViewSets handling CRUD | `wingz/interface/rest/views.py` — rides, ride events, users |
| Only the `admin` role can call the API | `IsAdminRole`, set as the project-wide default permission |
| Ride list endpoint | `GET /api/rides/` |
| Rider and driver included | nested, pulled in with `select_related` |
| Ride events included | `todays_ride_events`, see [the two rules about ride events](#the-two-rules-about-ride-events) |
| Pagination | 25 a page, `?page_size=` up to 100 |
| Filter by status and rider email | `?status=`, `?rider_email=` |
| Sort by pickup time and by distance | `?ordering=` on the same endpoint, both done in SQL |
| Sorting efficient on a big table | indexes for pickup time, bounding box for distance, measured on 200,000 rides |
| Pagination still works when sorting | sorting happens before `LIMIT`/`OFFSET`, and there's a test |
| `todays_ride_events`, last 24 hours | filtered `Prefetch` with `to_attr` |
| Never loads the full event list | the prefetch is capped by time, and I checked the SQL |
| Ride list in 2 queries, 3 with the count | verified, and tested to stay flat as rows grow |
| Table definitions followed | `db_table` and `db_column` on every model |
| Version control with a clean history | this repo |
| A thorough README | this file |
| Notes on design decisions | [Design notes](#design-notes) |
| Bonus reporting SQL | [The report](#the-report-trips-over-an-hour) |

On top of that: 88 tests, a production settings module, database-level coordinate
constraints, the Django admin, and management commands for demo data and the report.
