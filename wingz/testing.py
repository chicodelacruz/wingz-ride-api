"""Shared test helpers.

Lives in the package rather than under a tests/ directory because both the domain and
interface test suites import from it.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext

# Statements the database driver emits to manage transactions rather than to read or
# write data. ATOMIC_REQUESTS wraps every request in a transaction, and Django's
# TestCase wraps every test in one too, so a single request routinely captures a
# SAVEPOINT / RELEASE SAVEPOINT pair around the queries that actually matter.
TRANSACTION_BOOKKEEPING = (
    "SAVEPOINT",
    "RELEASE SAVEPOINT",
    "ROLLBACK TO SAVEPOINT",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
)


class CaptureRealQueries(CaptureQueriesContext):
    """Capture executed queries, excluding transaction bookkeeping.

    The assessment states the ride list should cost 2 queries (3 counting the
    pagination COUNT). Django's own ``assertNumQueries`` counts SAVEPOINT and RELEASE
    SAVEPOINT as queries, so asserting against it would mean writing a number that
    does not correspond to the requirement. This counts only the statements that hit
    tables, so the assertion in the test reads the same as the number in the spec.
    """

    def __init__(self, using=None):
        super().__init__(using or connection)

    @property
    def real_queries(self):
        return [
            query
            for query in self.captured_queries
            if not query["sql"].lstrip().upper().startswith(TRANSACTION_BOOKKEEPING)
        ]

    def __len__(self):
        return len(self.real_queries)

    def explain(self):
        """Readable dump of the captured statements, for debugging a failed count."""
        return "\n".join(f"{i}. {q['sql']}" for i, q in enumerate(self.real_queries, 1))
