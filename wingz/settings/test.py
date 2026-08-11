"""Test settings.

Kept separate from development so the query-count assertions never pick up local
debugging conveniences (SQL echoing, toolbars) that could change what gets executed.
Django's test runner forces DEBUG=False on its own, so this module does not need to.
"""

from wingz.settings.base import *  # noqa: F401,F403

# Fast, deterministic hashing: the fixtures create a lot of users and the default
# hasher dominates the runtime otherwise.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
