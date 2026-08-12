"""Populate the database with demonstration data.

Exists so the API can be exercised by hand, and so the reporting query has something
to report on. Not used by the test suite, which builds its own fixtures.

The random generator is seeded, so repeated runs with the same arguments produce the
same data — useful when comparing query plans or screenshots between runs.
"""

import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from wingz.domain.core.models import User
from wingz.domain.rides.models import Ride, RideEvent

DEMO_ADMIN_EMAIL = "admin@wingz.test"
DEMO_PASSWORD = "demo-password-12345"

# Pickup points are scattered around Metro Manila so the distance sort has something
# meaningful to order. (latitude, longitude, label)
ANCHORS = [
    (14.5995, 120.9842, "Manila"),
    (14.5547, 121.0244, "Makati"),
    (14.6760, 121.0437, "Quezon City"),
    (14.5378, 121.0014, "Pasay"),
    (14.4791, 121.0198, "Paranaque"),
    (14.6349, 121.0388, "San Juan"),
]

FIRST_NAMES = ["Ada", "Chris", "Howard", "Randy", "Mei", "Jose", "Lin", "Sam", "Nora", "Piet"]
LAST_NAMES = ["Reyes", "Harper", "Yamada", "Wilson", "Cruz", "Santos", "Ali", "Novak"]


class Command(BaseCommand):
    help = "Create demonstration users, rides and ride events."

    def add_arguments(self, parser):
        parser.add_argument("--rides", type=int, default=60, help="How many rides to create.")
        parser.add_argument("--riders", type=int, default=12)
        parser.add_argument("--drivers", type=int, default=6)
        parser.add_argument("--months", type=int, default=4, help="How far back rides should span.")
        parser.add_argument("--seed", type=int, default=20260812, help="Random seed.")
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing rides, events and demo users first. Superusers are kept.",
        )
        parser.add_argument(
            "--i-understand-this-destroys-data",
            action="store_true",
            dest="force",
            help="Required to run when DEBUG is False. Intended for staging, never production.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self._refuse_outside_development(options["force"])
        rng = random.Random(options["seed"])

        if options["clear"]:
            self._clear()
        elif Ride.objects.exists():
            # Seeding is additive. Saying so avoids the surprise of ending up with
            # twice the rides after a second run.
            self.stdout.write(
                self.style.WARNING(
                    f"{Ride.objects.count()} rides already exist; adding to them. " "Use --clear to start from empty."
                )
            )

        admin = self._ensure_admin()
        riders = self._create_users(rng, options["riders"], User.Role.RIDER)
        drivers = self._create_users(rng, options["drivers"], User.Role.DRIVER)
        rides = self._create_rides(rng, options["rides"], options["months"], riders, drivers)
        events = self._create_events(rng, rides)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write(f"  riders  : {len(riders)}")
        self.stdout.write(f"  drivers : {len(drivers)}")
        self.stdout.write(f"  rides   : {len(rides)}")
        self.stdout.write(f"  events  : {events}")
        self.stdout.write("")
        self.stdout.write("Admin login for the API and /admin/:")
        self.stdout.write(f"  email    : {admin.email}")
        self.stdout.write(f"  password : {DEMO_PASSWORD}")

    def _refuse_outside_development(self, force):
        """Refuse to run against anything that looks like a real deployment.

        This command deletes rides and creates an administrator whose password is
        committed to a public repository. Both are acceptable on a development
        machine and unacceptable anywhere real, so the safe behaviour is to fail
        loudly rather than rely on nobody ever running it in the wrong shell.
        """
        if settings.DEBUG or force:
            return

        raise CommandError(
            "DEBUG is False, so this looks like a deployed environment.\n"
            "seed_demo_data deletes ride data and creates an administrator whose "
            "password is public in this repository.\n"
            "If this really is a throwaway environment, re-run with "
            "--i-understand-this-destroys-data."
        )

    def _clear(self):
        RideEvent.objects.all().delete()
        Ride.objects.all().delete()
        User.objects.filter(is_superuser=False).exclude(email=DEMO_ADMIN_EMAIL).delete()
        self.stdout.write(self.style.WARNING("Cleared existing rides, events and non-superusers."))

    def _ensure_admin(self):
        """Create — or repair — the demo administrator.

        The account is a full superuser, not merely staff. Django's admin index only
        lists models the user holds permissions for, so a staff account with no
        permissions can log in and see an empty page, which looks like a broken
        installation rather than a permissions setting.

        An existing account is upgraded rather than skipped, so re-running the command
        fixes an account created by an earlier version.
        """
        admin = User.objects.filter(email=DEMO_ADMIN_EMAIL).first()

        if admin:
            if not (admin.is_superuser and admin.is_staff):
                admin.is_superuser = True
                admin.is_staff = True
                admin.role = User.Role.ADMIN
                admin.save(update_fields=["is_superuser", "is_staff", "role"])
                self.stdout.write(self.style.WARNING("Upgraded the existing demo admin to superuser."))
            return admin

        return User.objects.create_superuser(
            email=DEMO_ADMIN_EMAIL,
            password=DEMO_PASSWORD,
            first_name="Demo",
            last_name="Admin",
        )

    def _create_users(self, rng, count, role):
        users = []
        for index in range(count):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            email = f"{role}{index + 1}@wingz.test"
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "phone_number": f"+639{rng.randint(100000000, 999999999)}",
                },
            )
            users.append(user)
        return users

    def _create_rides(self, rng, count, months, riders, drivers):
        now = timezone.now()
        rides = []

        for _ in range(count):
            latitude, longitude, _label = rng.choice(ANCHORS)
            # Jitter around the anchor so distances differ ride to ride. Roughly a few
            # kilometres at these latitudes.
            pickup_latitude = latitude + rng.uniform(-0.05, 0.05)
            pickup_longitude = longitude + rng.uniform(-0.05, 0.05)

            rides.append(
                Ride(
                    status=rng.choice(Ride.Status.values),
                    id_rider=rng.choice(riders),
                    id_driver=rng.choice(drivers),
                    pickup_latitude=round(pickup_latitude, 6),
                    pickup_longitude=round(pickup_longitude, 6),
                    dropoff_latitude=round(pickup_latitude + rng.uniform(-0.08, 0.08), 6),
                    dropoff_longitude=round(pickup_longitude + rng.uniform(-0.08, 0.08), 6),
                    pickup_time=now - timedelta(days=rng.randint(0, months * 30), hours=rng.randint(0, 23)),
                )
            )

        return Ride.objects.bulk_create(rides)

    def _create_events(self, rng, rides):
        """Give each ride a pickup/dropoff pair, and some rides a recent event.

        Trip durations straddle one hour on purpose, so the reporting query has both
        qualifying and non-qualifying trips to separate.
        """
        now = timezone.now()
        events = []

        for ride in rides:
            picked_up_at = ride.pickup_time + timedelta(minutes=rng.randint(0, 15))
            duration = timedelta(minutes=rng.choice([20, 35, 50, 65, 80, 95, 130]))

            events.append(
                RideEvent(
                    id_ride=ride,
                    description=RideEvent.PICKUP_DESCRIPTION,
                    created_at=picked_up_at,
                )
            )
            events.append(
                RideEvent(
                    id_ride=ride,
                    description=RideEvent.DROPOFF_DESCRIPTION,
                    created_at=picked_up_at + duration,
                )
            )

            # Roughly a third of rides also get activity inside the last 24 hours, so
            # todays_ride_events is neither always empty nor always populated.
            if rng.random() < 0.34:
                events.append(
                    RideEvent(
                        id_ride=ride,
                        description=rng.choice(["Driver assigned", "Rider notified", "Route recalculated"]),
                        created_at=now - timedelta(hours=rng.randint(0, 23)),
                    )
                )

        RideEvent.objects.bulk_create(events)
        return len(events)
