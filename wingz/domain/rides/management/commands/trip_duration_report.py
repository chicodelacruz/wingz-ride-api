"""Print the trips-over-one-hour report.

A convenience wrapper so the reporting SQL can be run without pasting it into psql.
The statement itself lives in wingz.domain.rides.reports.
"""

from django.core.management.base import BaseCommand

from wingz.domain.rides.reports import TRIPS_OVER_ONE_HOUR_SQL, trips_over_one_hour


class Command(BaseCommand):
    help = "Count trips longer than one hour, grouped by month and driver."

    def add_arguments(self, parser):
        parser.add_argument(
            "--show-sql",
            action="store_true",
            help="Print the SQL statement instead of running it.",
        )

    def handle(self, *args, **options):
        if options["show_sql"]:
            self.stdout.write(TRIPS_OVER_ONE_HOUR_SQL.strip())
            return

        rows = trips_over_one_hour()

        if not rows:
            self.stdout.write(self.style.WARNING("No trips longer than one hour were found."))
            return

        header = f"{'Month':<10} {'Driver':<20} {'Count of Trips > 1 hr':>22}"
        self.stdout.write("")
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        for month, driver, count in rows:
            self.stdout.write(f"{month:<10} {driver:<20} {count:>22}")

        self.stdout.write("-" * len(header))
        self.stdout.write(f"{'':<10} {'total':<20} {sum(row[2] for row in rows):>22}")
        self.stdout.write("")
