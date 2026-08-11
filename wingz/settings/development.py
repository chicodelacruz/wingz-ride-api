"""Local development settings."""

import os

from wingz.settings.base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Echo every SQL statement to the console. Opt-in via WINGZ_SQL_LOG=1, because it is
# invaluable when checking the ride list's query count and unbearable the rest of the
# time.
SQL_LOG = os.getenv("WINGZ_SQL_LOG", "0") == "1"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG" if SQL_LOG else "INFO",
            "propagate": False,
        },
    },
}
