"""Base settings for the Wingz ride API.

Each architectural layer (domain / interface) contributes its own settings module,
which are merged here. Environment-specific modules (development.py, test.py) import
from this one and override as needed. Always run with an explicit
``--settings=wingz.settings.<env>``.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from wingz.domain.settings import *  # noqa: F401,F403
from wingz.interface.settings import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DJANGO_ROOT = Path(__file__).resolve().parent.parent  # .../wingz-ride-api/wingz
SITE_ROOT = DJANGO_ROOT.parent  # project root (contains manage.py)

# Load a gitignored .env from the project root if present. Real process env vars win:
# load_dotenv does not override keys that are already set.
load_dotenv(SITE_ROOT / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
# The fallback is deliberately long enough for HS256 (32+ bytes); a shorter one makes
# PyJWT emit InsecureKeyLengthWarning on every token it signs.
SECRET_KEY = os.getenv("WINGZ_SECRET_KEY", "dev-insecure-change-me-not-for-production")
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

AUTH_USER_MODEL = "core.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_URLCONF = "wingz.urls"
WSGI_APPLICATION = "wingz.wsgi.application"

# ---------------------------------------------------------------------------
# Applications (composed from the layer settings modules)
# ---------------------------------------------------------------------------
DJANGO_CONTRIB_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

INSTALLED_APPS = [
    *WINGZ_DOMAIN_INSTALLED_APPS,  # noqa: F405
    *DJANGO_CONTRIB_APPS,
    *WINGZ_INTERFACE_INSTALLED_APPS,  # noqa: F405
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [SITE_ROOT / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# ATOMIC_REQUESTS keeps each request in a single transaction, which matters for an
# API that writes ride state — a failed request leaves no half-applied changes.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("WINGZ_DB_NAME", "wingz"),
        "USER": os.getenv("WINGZ_DB_USER", "postgres"),
        "PASSWORD": os.getenv("WINGZ_DB_PASSWORD", ""),
        "HOST": os.getenv("WINGZ_DB_HOST", "localhost"),
        "PORT": os.getenv("WINGZ_DB_PORT", "5432"),
        "ATOMIC_REQUESTS": True,
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = SITE_ROOT / "staticfiles"
