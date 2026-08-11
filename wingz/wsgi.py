"""WSGI config for the Wingz ride API."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wingz.settings.development")

application = get_wsgi_application()
