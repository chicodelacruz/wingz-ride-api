"""Domain layer settings.

Each bounded context in the domain layer registers its AppConfig here.
"""

WINGZ_DOMAIN_INSTALLED_APPS = [
    "wingz.domain.core.apps.CoreAppConfig",
    "wingz.domain.rides.apps.RidesAppConfig",
]
