"""Tests for export_conditions.py.

Split in two on purpose.

The pure tests cover the decision that keeps an empty artifact from being
published, and the wire format the client depends on. They need nothing and
always run.

The database tests prove the thing a unit test cannot: that row-level
security really does turn a missing policy into *zero rows instead of an
error*. That is the failure this script exists to catch, and asserting it
against a real Postgres is the only way to know the catch works. They skip
when no database is reachable, the way backend/tests/test_pooler.py skips
without its pooler.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from export_conditions import (
    MAY_SELECT_SQL,
    POLICY_COUNT_SQL,
    PUBLIC_CLOSURES_SQL,
    RLS_ENABLED_SQL,
    _stamp_utc,
    assert_reader_permissions,
    build_document,
    connection_url,
    permission_problem,
    read_closures,
)

# Mirrors backend/app/models/closure.py closely enough to run the real query
# against. Deliberately NOT imported from the backend - nothing here may -
# which leaves a drift risk worth naming: a column renamed there breaks
# PUBLIC_CLOSURES_SQL in production while this table keeps the test green.
# Closing that properly is the contract test in #316; until then the column
# list here and `ClosureOut` are two places that have to agree by hand.
CLOSURES_DDL = """
    CREATE TABLE public.closures (
        id                VARCHAR PRIMARY KEY,
        reported_by       VARCHAR NOT NULL,
        reported_at       TIMESTAMP NOT NULL,
        trail_id          VARCHAR NOT NULL DEFAULT 'AT',
        start_mile_marker DOUBLE PRECISION NOT NULL,
        end_mile_marker   DOUBLE PRECISION NOT NULL,
        reason_type       VARCHAR(20) NOT NULL,
        note              TEXT,
        status            VARCHAR(20) NOT NULL DEFAULT 'closed',
        moderation_status VARCHAR(20) NOT NULL DEFAULT 'submitted',
        verified_by       VARCHAR,
        verified_at       TIMESTAMP,
        closed_since      TIMESTAMP,
        expected_reopen   TIMESTAMP,
        reroute_url       VARCHAR
    )
"""


# ---------------------------------------------------------------- pure tests


def test_a_missing_grant_is_refused_by_name():
    problem = permission_problem(may_select=False, rls_enabled=True, policies=1)

    assert problem is not None
    assert "GRANT SELECT" in problem


def test_rls_on_with_no_readable_policy_is_refused():
    """The case the whole script is built around: everything looks configured,
    the query succeeds, and it returns nothing."""
    problem = permission_problem(may_select=True, rls_enabled=True, policies=0)

    assert problem is not None
    assert "empty artifact" in problem


def test_no_policy_is_fine_when_rls_is_off():
    """Local development and CI, where the suite owns the table and never turns
    RLS on. Demanding a policy there would fail on a database that is not
    hiding anything."""
    assert permission_problem(may_select=True, rls_enabled=False, policies=0) is None


def test_a_grant_and_a_policy_together_pass():
    assert permission_problem(may_select=True, rls_enabled=True, policies=1) is None


def test_a_naive_timestamp_leaves_stamped_as_utc():
    """Storage is naive-UTC; the wire is not. An unstamped value is read as
    LOCAL by `new Date()`, which moves every closure by the reader's offset -
    four to five hours along this trail."""
    assert _stamp_utc(datetime(2026, 8, 1, 12, 0, 0)) == "2026-08-01T12:00:00Z"


def test_an_aware_timestamp_is_converted_rather_than_relabelled():
    eastern = timezone(timedelta(hours=-4))

    assert _stamp_utc(datetime(2026, 8, 1, 8, 0, 0, tzinfo=eastern)) == "2026-08-01T12:00:00Z"


def test_a_missing_timestamp_stays_missing():
    """`expected_reopen` is null far more often than not, and the client omits
    the line entirely rather than rendering "unknown"."""
    assert _stamp_utc(None) is None


def test_the_document_carries_when_it_was_built():
    """`generated_at` is what the client renders as "as of <date>", and the
    only thing that would reveal a bake job that silently stopped."""
    document = build_document([], datetime(2026, 8, 8, 6, 0, 0, tzinfo=timezone.utc))

    assert document["generated_at"] == "2026-08-08T06:00:00Z"
    assert document["closures"] == []


def test_a_sqlalchemy_style_url_is_accepted(monkeypatch):
    """The likeliest way to configure this secret is by copying the shape of
    UA_MIGRATION_DATABASE_URL, which names the driver because SQLAlchemy needs
    it. Raw psycopg does not understand that suffix."""
    monkeypatch.setenv("CONDITIONS_DATABASE_URL", "postgresql+psycopg://u:p@host:5432/db")

    assert connection_url() == "postgresql://u:p@host:5432/db"


def test_a_missing_url_says_so_rather_than_failing_to_connect(monkeypatch):
    monkeypatch.delenv("CONDITIONS_DATABASE_URL", raising=False)

    with pytest.raises(SystemExit) as exc:
        connection_url()

    assert "CONDITIONS_DATABASE_URL" in str(exc.value)


# ------------------------------------------------------------ database tests

ADMIN_URL = os.environ.get("PIPELINE_TEST_DATABASE_URL", "postgresql://ourhike:ourhike@localhost:5432/ourhike_dev")
SCRATCH_DB = "ourhike_conditions_test"


def _admin_connection():
    return psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3)


SCRATCH_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{SCRATCH_DB}"

# The role the RLS tests connect as, matching what production creates. Its
# password is a fixture detail: this role exists only inside the scratch
# database, for the length of one test session.
READER = "ourhike_conditions_reader_test"
READER_PASSWORD = "conditions-test-only"


@pytest.fixture(scope="module")
def conditions_db():
    """A scratch database with a `closures` table, dropped afterwards.

    Its own database rather than `ourhike_test`, which the backend suite drops
    tables from freely - two suites sharing one database is a race the moment
    anything runs them together.
    """
    try:
        with _admin_connection() as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")
            conn.execute(f"CREATE DATABASE {SCRATCH_DB}")
    except psycopg.OperationalError as exc:
        pytest.skip(f"no Postgres to test against ({exc.__class__.__name__}) - run backend/scripts/local-postgres.sh")

    with psycopg.connect(SCRATCH_URL, autocommit=True) as conn:
        conn.execute(CLOSURES_DDL)
        yield conn

    with _admin_connection() as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")


@pytest.fixture
def clean_closures(conditions_db):
    conditions_db.execute("TRUNCATE public.closures")
    conditions_db.execute("ALTER TABLE public.closures NO FORCE ROW LEVEL SECURITY")
    conditions_db.execute("ALTER TABLE public.closures DISABLE ROW LEVEL SECURITY")
    conditions_db.execute("DROP POLICY IF EXISTS conditions_reader_closures ON public.closures")
    return conditions_db


@pytest.fixture
def rls_subject(clean_closures):
    """A connection row-level security actually applies to.

    **This fixture is the whole reason the RLS tests are trustworthy, and it
    exists because the obvious shortcut is wrong in a way that passes
    locally.** The first version of these tests used
    `FORCE ROW LEVEL SECURITY` to make RLS bind the table's owner, since the
    suite had no second role to be. That works on a developer machine and is
    a no-op on CI: the postgres service container makes its `POSTGRES_USER` a
    SUPERUSER, and a superuser bypasses row security outright - FORCE binds
    the *owner*, and a superuser is not stopped by being one. Green locally,
    red on CI, and the difference was the privilege of the connecting role.

    So this connects as a real non-owner, non-superuser role, which is what
    production has and what makes RLS bind for the honest reason. Creating it
    needs CREATE ROLE - which CI's superuser has, and which the local role
    deliberately does not (`local-postgres.sh`: "not SUPERUSER, because
    production's role is not"). Where the role cannot be created, the test
    skips rather than quietly falling back to the weaker check: a proof that
    silently downgrades is how this got through the first time.
    """
    try:
        clean_closures.execute(f"DROP ROLE IF EXISTS {READER}")
        clean_closures.execute(f"CREATE ROLE {READER} LOGIN PASSWORD '{READER_PASSWORD}'")
    except psycopg.errors.InsufficientPrivilege:
        pytest.skip(
            "the connecting role cannot CREATE ROLE, so RLS cannot be exercised against a non-owner. "
            "CI's postgres service runs these; to run them locally, point "
            "PIPELINE_TEST_DATABASE_URL at a superuser - the Debian cluster's own `postgres` role "
            'will do once it has a password (`sudo -u postgres psql -c "ALTER ROLE postgres WITH PASSWORD ..."`).'
        )

    clean_closures.execute(f"GRANT USAGE ON SCHEMA public TO {READER}")
    clean_closures.execute(f"GRANT SELECT ON public.closures TO {READER}")

    reader_url = SCRATCH_URL.split("://", 1)[1].split("@", 1)[1]
    with psycopg.connect(f"postgresql://{READER}:{READER_PASSWORD}@{reader_url}", autocommit=True) as conn:
        yield conn

    # The policy goes first, and not for tidiness: a policy naming this role
    # is a dependency on it, and DROP ROLE fails outright while one exists.
    # `clean_closures` also drops it, but that runs before the *next* test
    # rather than after this one, which is too late to help here.
    clean_closures.execute("DROP POLICY IF EXISTS conditions_reader_closures ON public.closures")
    clean_closures.execute(f"REVOKE ALL ON public.closures FROM {READER}")
    clean_closures.execute(f"REVOKE ALL ON SCHEMA public FROM {READER}")
    clean_closures.execute(f"DROP ROLE IF EXISTS {READER}")


def _insert(conn, *, closure_id, moderation_status, mile=10.0):
    conn.execute(
        """
        INSERT INTO public.closures
            (id, reported_by, reported_at, start_mile_marker, end_mile_marker,
             reason_type, status, moderation_status, verified_by, verified_at)
        VALUES (%s, %s, %s, %s, %s, 'storm_damage', 'closed', %s, %s, %s)
        """,
        (
            closure_id,
            "reporter-profile-id",
            datetime(2026, 8, 1, 12, 0, 0),
            mile,
            mile + 1,
            moderation_status,
            "verifier-profile-id",
            datetime(2026, 8, 2, 12, 0, 0),
        ),
    )


def test_only_verified_closures_are_exported(clean_closures):
    """`moderation_status == verified` is the public/private line, and it is
    the whole reason this artifact can be published at all."""
    _insert(clean_closures, closure_id="yes", moderation_status="verified", mile=10.0)
    _insert(clean_closures, closure_id="no", moderation_status="submitted", mile=20.0)

    exported = read_closures(clean_closures)

    assert [row["id"] for row in exported] == ["yes"]


def test_the_export_names_nobody(clean_closures):
    """#430, enforced a second time on the way out. The reader role is not
    granted `profiles`, so these could not be resolved to a name - but the ids
    are themselves the join key, and a published artifact is permanent."""
    _insert(clean_closures, closure_id="c1", moderation_status="verified")

    [row] = read_closures(clean_closures)

    assert "reported_by" not in row
    assert "verified_by" not in row
    assert "reporter-profile-id" not in json.dumps(build_document([row], datetime.now(timezone.utc)))


def test_exported_timestamps_are_stamped(clean_closures):
    _insert(clean_closures, closure_id="c1", moderation_status="verified")

    [row] = read_closures(clean_closures)

    assert row["reported_at"] == "2026-08-01T12:00:00Z"
    assert row["verified_at"] == "2026-08-02T12:00:00Z"


def test_row_level_security_turns_a_missing_policy_into_silence(clean_closures, rls_subject):
    """The failure this script exists to catch, reproduced rather than argued.

    A verified closure is present and readable by the reader. Turning RLS on
    with no policy makes the identical query return **zero rows and no
    error** - which, published, is an empty artifact and a hiker shown no
    closure warnings.

    Read as the non-owner reader, not as the owner, for the reason `rls_subject`
    records at length: RLS exempts the owner, and a superuser is exempt even
    from FORCE.
    """
    _insert(clean_closures, closure_id="c1", moderation_status="verified")
    assert len(read_closures(rls_subject)) == 1

    clean_closures.execute("ALTER TABLE public.closures ENABLE ROW LEVEL SECURITY")

    assert read_closures(rls_subject) == []

    with pytest.raises(SystemExit) as exc:
        assert_reader_permissions(rls_subject)
    assert "empty artifact" in str(exc.value)


def test_a_policy_restores_the_rows_it_is_written_for(clean_closures, rls_subject):
    """The fix, proved against the same database - so the SQL in
    features/CONDITIONS_DELIVERY.md is verified rather than asserted.

    Note there is no FORCE here and none is needed: the reader is not the
    table's owner, which is exactly the situation production is in.
    """
    _insert(clean_closures, closure_id="c1", moderation_status="verified", mile=10.0)
    _insert(clean_closures, closure_id="c2", moderation_status="submitted", mile=20.0)
    clean_closures.execute("ALTER TABLE public.closures ENABLE ROW LEVEL SECURITY")
    clean_closures.execute(
        f"""
        CREATE POLICY conditions_reader_closures ON public.closures
            FOR SELECT TO {READER} USING (moderation_status = 'verified')
        """
    )

    assert_reader_permissions(rls_subject)

    assert [row["id"] for row in read_closures(rls_subject)] == ["c1"]


def test_the_catalog_queries_answer_against_a_real_schema(clean_closures):
    """The three SQL constants, run for real. A typo in one of them would
    otherwise only show up against production, where it fails open."""
    with clean_closures.cursor() as cur:
        cur.execute(MAY_SELECT_SQL)
        assert cur.fetchone()[0] is True

        cur.execute(RLS_ENABLED_SQL)
        assert cur.fetchone()[0] is False

        cur.execute(POLICY_COUNT_SQL)
        assert cur.fetchone()[0] == 0

    with clean_closures.cursor() as cur:
        cur.execute(PUBLIC_CLOSURES_SQL)
        assert [d.name for d in cur.description] == [
            "id",
            "reported_at",
            "trail_id",
            "start_mile_marker",
            "end_mile_marker",
            "reason_type",
            "note",
            "status",
            "moderation_status",
            "verified_at",
            "closed_since",
            "expected_reopen",
            "reroute_url",
        ]
