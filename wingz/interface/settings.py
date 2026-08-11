"""Interface (REST) layer settings."""

from datetime import timedelta

WINGZ_INTERFACE_INSTALLED_APPS = [
    "rest_framework",
    "django_filters",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # Every endpoint is admin-only by default; the permission is declared once here
    # rather than repeated on each ViewSet, so a new endpoint cannot accidentally
    # ship unprotected.
    "DEFAULT_PERMISSION_CLASSES": [
        "wingz.interface.rest.permissions.IsAdminRole",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "wingz.interface.rest.pagination.RidePageNumberPagination",
    "PAGE_SIZE": 25,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    # The User primary key is `id_user`, not Django's default `id`. Without this,
    # simplejwt raises AttributeError when minting a token and no one can log in.
    "USER_ID_FIELD": "id_user",
    "USER_ID_CLAIM": "user_id",
}
