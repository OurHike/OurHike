"""Each parallel worker gets its own database, and nothing else moves.

The gotcha this guards, per TESTING.md's core rule, is a measured one rather
than a hypothetical. `conftest.py`'s isolation model is "drop every table
between tests", which is safe exactly as long as one process is doing it.
Pointed at one database, four `pytest -n` workers do not merely fail - they
wedge, each blocking on locks held by tables another worker is partway
through dropping. The run that found this took 1785s before it was killed,
against 60s for the same suite serially.

The fix is a database per worker, and it is one line of URL rewriting, which
is the kind of thing that looks obviously correct and silently stops
happening. These tests are what make it stay true: the first three pin the
rewrite, and the last one checks it actually took effect in the process
running right now - because a rewrite that quietly became a no-op would put
every worker back on one database and buy back the deadlock.
"""

from __future__ import annotations

import os

from sqlalchemy.engine import make_url

from app.config import settings
from tests.conftest import _worker_database_url

SERIAL_URL = "postgresql+psycopg://ourhike:ourhike@localhost:5432/ourhike_test"


def test_the_worker_name_lands_on_the_database_and_nowhere_else():
    """Only the database changes - the server it is on must not.

    Rewriting the wrong component is the failure that would not look like
    one: a URL pointing at a different host fails loudly, but one that
    silently kept the shared database name would pass this file's siblings
    and deadlock the moment somebody ran with `-n`.
    """
    rewritten = make_url(_worker_database_url(SERIAL_URL, "gw0"))
    original = make_url(SERIAL_URL)

    assert rewritten.database == "ourhike_test_gw0"
    assert rewritten.host == original.host
    assert rewritten.port == original.port
    assert rewritten.username == original.username
    assert rewritten.password == original.password
    assert rewritten.drivername == original.drivername


def test_two_workers_never_land_on_the_same_database():
    """The invariant the whole change exists for, stated directly.

    Everything else here is detail; this is the property that makes parallel
    running safe at all, so it is asserted on its own rather than left to be
    inferred from the naming test above.
    """
    databases = {make_url(_worker_database_url(SERIAL_URL, f"gw{n}")).database for n in range(8)}

    assert len(databases) == 8


def test_a_url_carrying_no_database_is_still_rewritten_per_worker():
    """CI passes DATABASE_URL in, so the input is not always the default.

    A URL whose database is absent must not collapse every worker onto one
    name - that is the deadlock again, arriving through a code path nobody
    ran locally.
    """
    without = "postgresql+psycopg://ourhike:ourhike@localhost:5432/"

    first = make_url(_worker_database_url(without, "gw0")).database
    second = make_url(_worker_database_url(without, "gw1")).database

    assert first != second


def test_this_process_is_really_on_the_database_its_worker_was_given():
    """Guards the guard: the rewrite above is wired up, not just correct.

    The three tests above would all pass on a `conftest.py` that computed the
    per-worker URL and then never applied it, which is the shape this is here
    to catch. Serially there is no worker and the URL is the plain one, and
    asserting that is worth as much - it is what says the parallel path stays
    out of the way of an ordinary `pytest` run.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    database = make_url(settings.database_url).database or ""

    if worker:
        assert database.endswith(f"_{worker}")
    else:
        assert not database.startswith("ourhike_test_gw")
