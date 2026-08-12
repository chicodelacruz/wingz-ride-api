"""Production settings.

Nothing here has a permissive default. Anything that would be unsafe if left unset —
the secret key, the allowed hosts — raises at startup instead, on the principle that a
deployment refusing to boot is better than one quietly running with a development
secret.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from wingz.settings.base import *  # noqa: F401,F403

DEBUG = False


def _required(name):
    value = os.getenv(name)
    if not value:
        raise ImproperlyConfigured(f"{name} must be set in production.")
    return value


SECRET_KEY = _required("WINGZ_SECRET_KEY")
ALLOWED_HOSTS = [host.strip() for host in _required("WINGZ_ALLOWED_HOSTS").split(",") if host.strip()]

# ---------------------------------------------------------------------------
# Transport security
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # one year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Behind a load balancer or reverse proxy that terminates TLS, Django sees plain HTTP
# on the internal hop. This header is how it learns the original request was secure —
# it must only be trusted when such a proxy is actually in front, because a client
# could otherwise set it themselves.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
# JSON only. The browsable API is a development convenience; in production it is
# extra attack surface and renders HTML no client asked for.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Reuse connections rather than opening one per request. Must stay below the
# idle timeout of any connection pooler sitting in front of PostgreSQL.
DATABASES["default"]["CONN_MAX_AGE"] = 60  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Log to stdout so the platform collects it, rather than to files this process
# would have to rotate itself.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
