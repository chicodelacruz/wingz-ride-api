"""The seed command must not be runnable against a deployed environment.

It deletes ride data and creates an administrator whose password is committed to a
public repository, so the guard matters more than the seeding itself.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from wingz.domain.core.models import User
from wingz.domain.rides.models import Ride


@pytest.mark.django_db
class TestSeedCommandGuard:
    @override_settings(DEBUG=False)
    def test_refuses_to_run_when_debug_is_false(self):
        with pytest.raises(CommandError, match="DEBUG is False"):
            call_command("seed_demo_data", rides=1)

        assert not Ride.objects.exists()
        assert not User.objects.filter(email="admin@wingz.test").exists()

    @override_settings(DEBUG=False)
    def test_explicit_override_is_honoured(self):
        """An escape hatch for throwaway staging, deliberately verbose to type."""
        call_command("seed_demo_data", rides=2, riders=2, drivers=1, force=True)

        assert Ride.objects.count() == 2

    @override_settings(DEBUG=True)
    def test_runs_normally_in_development(self):
        call_command("seed_demo_data", rides=2, riders=2, drivers=1)

        assert Ride.objects.count() == 2
        assert User.objects.get(email="admin@wingz.test").is_superuser
