"""The engine really does survive a transaction pooler.

tests/test_engine_options.py asserts which options are chosen. This asserts
that those options are the right ones, against a pooler that behaves the way
Supabase's does - because "we pass prepare_threshold=None" and "the API stays
up on the pooled connection string" are different claims, and only the second
one is what #95 was about.

Skipped unless POOLER_DATABASE_URL names a transaction-mode pooler;
`scripts/local-pooler.sh` starts one and prints the URL, and CI's backend
workflow does the same. It is opt-in rather than always-on because it needs
software the rest of the suite does not, and a suite that cannot run without
pgbouncer installed would be a worse trade than a test that says when it was
skipped.
"""

import os

import pytest
from sqlalchemy import create_engine, text

from app.db.session import engine_options

POOLER_URL = os.environ.get("POOLER_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not POOLER_URL,
    reason="POOLER_DATABASE_URL is unset - run scripts/local-pooler.sh to exercise this",
)

# Two clients, interleaved, well past psycopg's 5-execution threshold. One
# client alone can be handed the same backend every time and never notice.
CLIENTS = 2
ROUNDS = 12
PROBE = text("select count(*) from pg_class where relname = :name")


def _run_traffic(*, prepared_statements: bool) -> None:
    """Interleave transactions from two connections through the pooler.

    Each `commit()` returns the server connection to the pooler, which is the
    moment a transaction pooler is free to hand the next one to a different
    backend - the whole point of the exercise.
    """
    options = engine_options(POOLER_URL, prepared_statements=prepared_statements)
    engines = [create_engine(POOLER_URL, pool_size=1, **options) for _ in range(CLIENTS)]
    connections = [engine.connect() for engine in engines]
    try:
        for _ in range(ROUNDS):
            for connection in connections:
                connection.execute(PROBE, {"name": "pg_class"}).scalar_one()
                connection.commit()
    finally:
        for connection in connections:
            connection.close()
        for engine in engines:
            engine.dispose()


def test_the_apps_own_engine_options_survive_a_transaction_pooler():
    """The claim that matters: production stays up on the pooled URL."""
    _run_traffic(prepared_statements=False)


def test_prepared_statements_really_do_break_here():
    """Proof the test above is not passing for free.

    Without this, `prepare_threshold=None` could be deleted from
    app/db/session.py and the test above would still pass on any environment
    where the pooler is not actually shuffling backends - a green suite
    asserting nothing. The failure is psycopg's, not this repository's, so
    the assertion is on the error rather than on an exception type of our
    own.
    """
    with pytest.raises(Exception) as caught:  # noqa: PT011 - psycopg's, see docstring
        _run_traffic(prepared_statements=True)

    message = str(caught.value).lower()
    assert "prepared statement" in message, (
        "Expected psycopg's prepared-statement failure through the pooler, got:\n"
        f"  {caught.value}\n"
        "If POOLER_DATABASE_URL points at a session-mode pooler, or at a pgbouncer "
        "with max_prepared_statements > 0, this hazard is not being reproduced and "
        "the test above proves nothing. See scripts/local-pooler.sh."
    )
