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

Reports get the same treatment as closures plus one test closures cannot
have: the predicate is two columns, and the row that must never appear is a
`bad_hikers` report - the one type that reports on *people*. A published
artifact cannot be recalled, so that exclusion is asserted directly rather
than inferred from the predicate looking right.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

import export_conditions
from export_conditions import (
    MAY_SELECT_SQL,
    PENDING_READER_SETUP,
    POLICY_COUNT_SQL,
    PUBLIC_CLOSURES_SQL,
    PUBLIC_NOTES_SQL,
    PUBLIC_REPORTS_SQL,
    RLS_ENABLED_SQL,
    TABLE_EXISTS_SQL,
    _stamp_utc,
    assert_reader_permissions,
    build_document,
    connection_url,
    permission_problem,
    read_closures,
    read_notes,
    read_reports,
    reader_problem,
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
        reroute_url       VARCHAR,
        start_lat         DOUBLE PRECISION,
        start_lon         DOUBLE PRECISION,
        end_lat           DOUBLE PRECISION,
        end_lon           DOUBLE PRECISION
    )
"""

# Mirrors backend/app/models/report.py, with the same drift caveat as above.
# `"timestamp"` is quoted for the reason PUBLIC_REPORTS_SQL quotes it.
REPORTS_DDL = """
    CREATE TABLE public.reports (
        id            VARCHAR PRIMARY KEY,
        reporter_id   VARCHAR NOT NULL,
        type          VARCHAR(20) NOT NULL,
        poi_id        VARCHAR,
        lat           DOUBLE PRECISION,
        lon           DOUBLE PRECISION,
        mile          DOUBLE PRECISION,
        reporter_type VARCHAR(20) NOT NULL,
        "timestamp"   TIMESTAMP NOT NULL,
        received_at   TIMESTAMP NOT NULL,
        note          TEXT,
        photo_url     VARCHAR,
        follow_up     JSON,
        status        VARCHAR(20) NOT NULL DEFAULT 'submitted',
        visibility    VARCHAR(20) NOT NULL,
        severity      VARCHAR(20) NOT NULL DEFAULT 'normal',
        verified_by   VARCHAR,
        verified_at   TIMESTAMP,
        maintainer_id VARCHAR,
        club_id       VARCHAR
    )
"""


# Mirrors backend/app/models/field_note.py, with the drift caveat the two
# DDLs above carry - and the same enforcement closing it:
# backend/tests/test_conditions_publisher_contract.py compares the SQL's
# column list against the served FieldNoteOut schema.
FIELD_NOTES_DDL = """
    CREATE TABLE public.field_notes (
        id            VARCHAR PRIMARY KEY,
        reporter_id   VARCHAR NOT NULL,
        poi_id        VARCHAR,
        lat           DOUBLE PRECISION,
        lon           DOUBLE PRECISION,
        mile          DOUBLE PRECISION,
        observation   VARCHAR(20),
        note          TEXT,
        observed_at   TIMESTAMP NOT NULL,
        posted_at     TIMESTAMP NOT NULL,
        reporter_type VARCHAR(20) NOT NULL,
        hidden_at     TIMESTAMP,
        hidden_by     VARCHAR
    )
"""


# ---------------------------------------------------------------- pure tests


def test_a_missing_grant_is_refused_by_name():
    problem = permission_problem("closures", exists=True, may_select=False, rls_enabled=True, policies=1)

    assert problem is not None
    assert "GRANT SELECT" in problem
    assert "closures" in problem


def test_rls_on_with_no_readable_policy_is_refused():
    """The case the whole script is built around: everything looks configured,
    the query succeeds, and it returns nothing."""
    problem = permission_problem("closures", exists=True, may_select=True, rls_enabled=True, policies=0)

    assert problem is not None
    assert "empty artifact" in problem


def test_the_reports_refusal_quotes_the_reports_predicate():
    """The fix the message carries has to be the right fix for the table it
    names - the reports policy is two columns, and pasting the closures one
    would create a policy that leaks every submitted report."""
    problem = permission_problem("reports", exists=True, may_select=True, rls_enabled=True, policies=0)

    assert problem is not None
    assert "reports" in problem
    assert "status IN ('verified', 'resolved') AND visibility = 'public'" in problem


def test_no_policy_is_fine_when_rls_is_off():
    """Local development and CI, where the suite owns the table and never turns
    RLS on. Demanding a policy there would fail on a database that is not
    hiding anything."""
    assert permission_problem("closures", exists=True, may_select=True, rls_enabled=False, policies=0) is None


def test_a_grant_and_a_policy_together_pass():
    assert permission_problem("closures", exists=True, may_select=True, rls_enabled=True, policies=1) is None


def test_a_table_that_does_not_exist_is_named_as_a_missing_migration():
    """The production signature of #922. `field_notes` reached this reader
    before the migration that creates it reached the production database, and
    the check raised UndefinedTable from inside psycopg instead of saying so -
    a traceback where the point of this function is an actionable sentence."""
    problem = permission_problem("field_notes", exists=False, may_select=False, rls_enabled=False, policies=0)

    assert problem is not None
    assert "does not exist" in problem
    assert "migrate.yml" in problem
    # Not the grant message: the fix is a migration, and telling somebody to
    # GRANT on a table that is not there sends them to the wrong console.
    assert "GRANT SELECT" not in problem


def test_a_missing_table_is_reported_rather_than_raised(clean_tables):
    """`has_table_privilege` and the `::regclass` cast both raise on a relation
    that is not there, so the existence question has to come first and has to
    be the one that does not. Asked against a real Postgres, because that
    ordering is only load-bearing against a real catalog."""
    problem = reader_problem(clean_tables, "no_such_table_here")

    assert problem is not None
    assert "does not exist" in problem


def test_the_existence_query_answers_for_a_table_that_is_there(clean_tables):
    with clean_tables.cursor() as cur:
        cur.execute(TABLE_EXISTS_SQL, ("public.closures",))
        assert cur.fetchone()[0] is True

        cur.execute(TABLE_EXISTS_SQL, ("public.no_such_table_here",))
        assert cur.fetchone()[0] is False


def test_only_field_notes_may_be_pending_and_it_says_what_would_settle_it():
    """The set is scaffolding for a rollout window (#922), so it has to stay
    small and stay removable. Closures and reports must never be in it: they
    are configured in both environments today, so their failing is a
    regression and has to stay red."""
    assert set(PENDING_READER_SETUP) == {"field_notes"}
    assert "closures" not in PENDING_READER_SETUP
    assert "reports" not in PENDING_READER_SETUP

    guidance = PENDING_READER_SETUP["field_notes"]
    assert "d7e2b9c41f68" in guidance
    assert "CONDITIONS_DELIVERY.md" in guidance


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
    document = build_document("closures", [], datetime(2026, 8, 8, 6, 0, 0, tzinfo=timezone.utc))

    assert document["generated_at"] == "2026-08-08T06:00:00Z"
    assert document["closures"] == []


def test_each_document_names_its_own_payload():
    """`conditions/reports.json` holds `reports`, the way the live endpoint's
    path names what it answers with - the client validates the field by name
    before trusting the document."""
    document = build_document("reports", [], datetime(2026, 8, 8, 6, 0, 0, tzinfo=timezone.utc))

    assert document["reports"] == []
    assert "closures" not in document


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

POLICIES = {
    "closures": "conditions_reader_closures",
    "reports": "conditions_reader_reports",
    "field_notes": "conditions_reader_notes",
}


@pytest.fixture(scope="module")
def conditions_db():
    """A scratch database with `closures` and `reports` tables, dropped
    afterwards.

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
        conn.execute(REPORTS_DDL)
        conn.execute(FIELD_NOTES_DDL)
        yield conn

    with _admin_connection() as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")


@pytest.fixture
def clean_tables(conditions_db):
    for table, policy in POLICIES.items():
        conditions_db.execute(f"TRUNCATE public.{table}")
        conditions_db.execute(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY")
        conditions_db.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
        conditions_db.execute(f"DROP POLICY IF EXISTS {policy} ON public.{table}")
    return conditions_db


@pytest.fixture
def rls_subject(clean_tables):
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
        clean_tables.execute(f"DROP ROLE IF EXISTS {READER}")
        clean_tables.execute(f"CREATE ROLE {READER} LOGIN PASSWORD '{READER_PASSWORD}'")
    except psycopg.errors.InsufficientPrivilege:
        pytest.skip(
            "the connecting role cannot CREATE ROLE, so RLS cannot be exercised against a non-owner. "
            "CI's postgres service runs these; to run them locally, point "
            "PIPELINE_TEST_DATABASE_URL at a superuser - the Debian cluster's own `postgres` role "
            'will do once it has a password (`sudo -u postgres psql -c "ALTER ROLE postgres WITH PASSWORD ..."`).'
        )

    clean_tables.execute(f"GRANT USAGE ON SCHEMA public TO {READER}")
    clean_tables.execute(f"GRANT SELECT ON public.closures, public.reports, public.field_notes TO {READER}")

    reader_url = SCRATCH_URL.split("://", 1)[1].split("@", 1)[1]
    with psycopg.connect(f"postgresql://{READER}:{READER_PASSWORD}@{reader_url}", autocommit=True) as conn:
        yield conn

    # The policies go first, and not for tidiness: a policy naming this role
    # is a dependency on it, and DROP ROLE fails outright while one exists.
    # `clean_tables` also drops them, but that runs before the *next* test
    # rather than after this one, which is too late to help here.
    for table, policy in POLICIES.items():
        clean_tables.execute(f"DROP POLICY IF EXISTS {policy} ON public.{table}")
    clean_tables.execute(f"REVOKE ALL ON public.closures, public.reports, public.field_notes FROM {READER}")
    clean_tables.execute(f"REVOKE ALL ON SCHEMA public FROM {READER}")
    clean_tables.execute(f"DROP ROLE IF EXISTS {READER}")


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


def _insert_report(
    conn,
    *,
    report_id,
    status="verified",
    visibility="public",
    report_type="blowdown",
    written=datetime(2026, 8, 1, 9, 0, 0),
):
    """One report with every withheld field populated, so the exclusion tests
    assert against real values rather than against nulls that were never
    going to leak anyway."""
    conn.execute(
        """
        INSERT INTO public.reports
            (id, reporter_id, type, lat, lon, mile, reporter_type, "timestamp",
             received_at, note, photo_url, status, visibility, severity,
             verified_by, verified_at, maintainer_id, club_id)
        VALUES (%s, 'reporter-profile-id', %s, 41.2, -74.1, 1407.2, 'thru', %s,
                %s, 'a note', 'photo-object-key', %s, %s, 'serious',
                'verifier-profile-id', %s, 'maintainer-profile-id', 'club-1')
        """,
        (
            report_id,
            report_type,
            written,
            datetime(2026, 8, 4, 9, 0, 0),
            status,
            visibility,
            datetime(2026, 8, 2, 12, 0, 0),
        ),
    )


def test_only_verified_closures_are_exported(clean_tables):
    """`moderation_status == verified` is the public/private line, and it is
    the whole reason this artifact can be published at all."""
    _insert(clean_tables, closure_id="yes", moderation_status="verified", mile=10.0)
    _insert(clean_tables, closure_id="no", moderation_status="submitted", mile=20.0)

    exported = read_closures(clean_tables)

    assert [row["id"] for row in exported] == ["yes"]


def test_the_export_names_nobody(clean_tables):
    """#430, enforced a second time on the way out. The reader role is not
    granted `profiles`, so these could not be resolved to a name - but the ids
    are themselves the join key, and a published artifact is permanent."""
    _insert(clean_tables, closure_id="c1", moderation_status="verified")

    [row] = read_closures(clean_tables)

    assert "reported_by" not in row
    assert "verified_by" not in row
    assert "reporter-profile-id" not in json.dumps(build_document("closures", [row], datetime.now(timezone.utc)))


def test_exported_timestamps_are_stamped(clean_tables):
    _insert(clean_tables, closure_id="c1", moderation_status="verified")

    [row] = read_closures(clean_tables)

    assert row["reported_at"] == "2026-08-01T12:00:00Z"
    assert row["verified_at"] == "2026-08-02T12:00:00Z"


def test_moderated_public_reports_are_exported_and_submitted_ones_are_not(clean_tables):
    """`resolved` stays public deliberately - it was verified once and reads
    as "Fixed" - while `submitted` leaking is the difference between
    verification being a gate and being a label on something already public."""
    _insert_report(clean_tables, report_id="r-verified", status="verified", written=datetime(2026, 8, 1, 9, 0, 0))
    _insert_report(clean_tables, report_id="r-resolved", status="resolved", written=datetime(2026, 8, 2, 9, 0, 0))
    _insert_report(clean_tables, report_id="r-submitted", status="submitted", written=datetime(2026, 8, 3, 9, 0, 0))
    _insert_report(clean_tables, report_id="r-dismissed", status="dismissed", written=datetime(2026, 8, 4, 9, 0, 0))

    exported = read_reports(clean_tables)

    assert [row["id"] for row in exported] == ["r-verified", "r-resolved"]


def test_a_bad_hikers_report_and_a_thanks_never_appear(clean_tables):
    """The one test #436 says this cannot ship without. A `bad_hikers` report
    is about a person and routes `internal_only`; a `thanks` is `club_only`.
    Both are inserted VERIFIED, so the only thing keeping each out is the
    `visibility` half of the predicate - the half closures do not have, and
    the reason reports were not simply copied from them.
    """
    _insert_report(clean_tables, report_id="about-a-person", report_type="bad_hikers", visibility="internal_only")
    _insert_report(clean_tables, report_id="a-thanks", report_type="thanks", visibility="club_only")
    _insert_report(clean_tables, report_id="a-blowdown", report_type="blowdown", visibility="public")

    exported = read_reports(clean_tables)

    assert [row["id"] for row in exported] == ["a-blowdown"]
    document = json.dumps(build_document("reports", exported, datetime.now(timezone.utc)))
    assert "about-a-person" not in document
    assert "a-thanks" not in document


def test_the_reports_export_names_nobody_and_carries_no_photo(clean_tables):
    """The anonymous `ReportOut` withholds `reporter_id`, `received_at`,
    `maintainer_id` and `club_id`, never sends `verified_by`/`verified_at`,
    and the baked artifact drops `photo_url` too - a presigned URL expires in
    minutes, the artifact lives a day, and the object key underneath points
    into a private bucket (#436). The live tier supplies photos."""
    _insert_report(clean_tables, report_id="r1")

    [row] = read_reports(clean_tables)

    for withheld in ("reporter_id", "received_at", "maintainer_id", "club_id", "verified_by", "verified_at", "photo_url"):
        assert withheld not in row
    document = json.dumps(build_document("reports", [row], datetime.now(timezone.utc)))
    assert "reporter-profile-id" not in document
    assert "verifier-profile-id" not in document
    assert "photo-object-key" not in document


def test_exported_report_timestamps_are_stamped(clean_tables):
    _insert_report(clean_tables, report_id="r1", written=datetime(2026, 8, 1, 9, 0, 0))

    [row] = read_reports(clean_tables)

    assert row["timestamp"] == "2026-08-01T09:00:00Z"


def _insert_note(
    conn,
    *,
    note_id,
    poi_id="osm_water:1",
    observation="dry",
    observed=None,
    hidden=False,
):
    conn.execute(
        """
        INSERT INTO public.field_notes
            (id, reporter_id, poi_id, lat, lon, mile, observation, note,
             observed_at, posted_at, reporter_type, hidden_at, hidden_by)
        VALUES (%s, %s, %s, 41.2, -74.1, 1382.4, %s, 'a word for the next hiker',
                %s, %s, 'thru', %s, %s)
        """,
        (
            note_id,
            "note-author-profile-id",
            poi_id,
            observation,
            observed if observed is not None else datetime.now(timezone.utc) - timedelta(days=1),
            datetime.now(timezone.utc),
            datetime.now(timezone.utc) if hidden else None,
            "moderator-profile-id" if hidden else None,
        ),
    )


def test_a_hidden_note_never_reaches_the_artifact(clean_tables):
    """FIELD_NOTES.md §5's guarantee from the reports side, with the opposite
    default: notes publish on landing, so the ONE thing this predicate does
    is enforce a moderator's removal - and a removal that leaked would put
    the flagged content back in front of every hiker with the next bake."""
    _insert_note(clean_tables, note_id="n1")
    _insert_note(clean_tables, note_id="n2", observation="flowing", hidden=True)

    exported = read_notes(clean_tables)

    assert [row["id"] for row in exported] == ["n1"]


def test_the_notes_export_names_nobody_and_keeps_one_clock(clean_tables):
    """No reporter_id - many dated notes along a corridor from one identifier
    reconstruct a hike (#252's pair, refused here before the leak) - and no
    posted_at, the second clock ReportOut withholds as received_at."""
    _insert_note(clean_tables, note_id="n1")

    [row] = read_notes(clean_tables)

    for withheld in ("reporter_id", "posted_at", "hidden_at", "hidden_by", "recency_rank"):
        assert withheld not in row
    assert "note-author-profile-id" not in json.dumps(build_document("notes", [row], datetime.now(timezone.utc)))


def test_the_notes_export_keeps_each_places_most_recent_few(clean_tables):
    """The size rule (FIELD_NOTES.md §6): the bake carries the most recent K
    notes per POI inside a window, never the history - an artifact that grows
    without bound is a download that eventually fails on the trail."""
    for index in range(8):
        _insert_note(
            clean_tables,
            note_id=f"n{index}",
            observed=datetime.now(timezone.utc) - timedelta(days=index),
        )
    _insert_note(clean_tables, note_id="elsewhere", poi_id="atc_shelters:9")

    exported = read_notes(clean_tables)
    here = [row for row in exported if row["poi_id"] == "osm_water:1"]

    # 5 mirrors NOTES_PER_POI in backend/app/routers/field_notes.py - the
    # live read and the baseline must be the same document from two doors.
    assert len(here) == 5
    assert [row["id"] for row in exported if row["poi_id"] == "atc_shelters:9"] == ["elsewhere"]


def test_the_notes_export_drops_observations_older_than_the_window(clean_tables):
    _insert_note(clean_tables, note_id="old", observed=datetime.now(timezone.utc) - timedelta(days=120))
    _insert_note(clean_tables, note_id="fresh")

    exported = read_notes(clean_tables)

    assert [row["id"] for row in exported] == ["fresh"]


def test_exported_note_timestamps_are_stamped(clean_tables):
    _insert_note(clean_tables, note_id="n1", observed=datetime(2026, 8, 18, 9, 0, 0))

    [row] = read_notes(clean_tables)

    assert row["observed_at"] == "2026-08-18T09:00:00Z"


def test_the_notes_window_and_cap_mirror_the_backends(clean_tables):
    """Two files, two languages, one pair of numbers: the live endpoint's
    NOTES_WINDOW_DAYS/NOTES_PER_POI and this SQL's literals. Read as text the
    way the publisher contract test reads this file, so moving one without
    the other fails here rather than as a baseline quietly narrower or wider
    than the live overlay."""
    backend_router = (export_conditions.ROOT.parent / "backend" / "app" / "routers" / "field_notes.py").read_text()

    import re

    window = re.search(r"NOTES_WINDOW_DAYS = (\d+)", backend_router)
    per_poi = re.search(r"NOTES_PER_POI = (\d+)", backend_router)
    assert window and per_poi, "the backend's window/cap constants moved; fix this pairing test"
    assert f"interval '{window.group(1)} days'" in PUBLIC_NOTES_SQL
    assert f"recency_rank <= {per_poi.group(1)}" in PUBLIC_NOTES_SQL


def test_row_level_security_turns_a_missing_policy_into_silence(clean_tables, rls_subject):
    """The failure this script exists to catch, reproduced rather than argued.

    A verified closure is present and readable by the reader. Turning RLS on
    with no policy makes the identical query return **zero rows and no
    error** - which, published, is an empty artifact and a hiker shown no
    closure warnings.

    Read as the non-owner reader, not as the owner, for the reason `rls_subject`
    records at length: RLS exempts the owner, and a superuser is exempt even
    from FORCE.
    """
    _insert(clean_tables, closure_id="c1", moderation_status="verified")
    assert len(read_closures(rls_subject)) == 1

    clean_tables.execute("ALTER TABLE public.closures ENABLE ROW LEVEL SECURITY")

    assert read_closures(rls_subject) == []

    with pytest.raises(SystemExit) as exc:
        assert_reader_permissions(rls_subject, "closures")
    assert "empty artifact" in str(exc.value)


def test_a_policy_restores_the_rows_it_is_written_for(clean_tables, rls_subject):
    """The fix, proved against the same database - so the SQL in
    features/CONDITIONS_DELIVERY.md is verified rather than asserted.

    Note there is no FORCE here and none is needed: the reader is not the
    table's owner, which is exactly the situation production is in.
    """
    _insert(clean_tables, closure_id="c1", moderation_status="verified", mile=10.0)
    _insert(clean_tables, closure_id="c2", moderation_status="submitted", mile=20.0)
    clean_tables.execute("ALTER TABLE public.closures ENABLE ROW LEVEL SECURITY")
    clean_tables.execute(
        f"""
        CREATE POLICY conditions_reader_closures ON public.closures
            FOR SELECT TO {READER} USING (moderation_status = 'verified')
        """
    )

    assert_reader_permissions(rls_subject, "closures")

    assert [row["id"] for row in read_closures(rls_subject)] == ["c1"]


def test_the_reports_policy_lets_through_exactly_the_public_moderated_rows(clean_tables, rls_subject):
    """features/CONDITIONS_DELIVERY.md's reports policy, verified rather than
    asserted - and verified with a bare SELECT, not the exporter's own query,
    so this is the database refusing to show the reader a private row even if
    a future exporter edit forgot the WHERE clause entirely.
    """
    _insert_report(clean_tables, report_id="public-verified", status="verified", visibility="public")
    _insert_report(clean_tables, report_id="public-submitted", status="submitted", visibility="public")
    _insert_report(clean_tables, report_id="about-a-person", report_type="bad_hikers", visibility="internal_only")
    clean_tables.execute("ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY")
    clean_tables.execute(
        f"""
        CREATE POLICY conditions_reader_reports ON public.reports
            FOR SELECT TO {READER}
            USING (status IN ('verified', 'resolved') AND visibility = 'public')
        """
    )

    assert_reader_permissions(rls_subject, "reports")

    with rls_subject.cursor() as cur:
        cur.execute("SELECT id FROM public.reports")
        assert [row[0] for row in cur.fetchall()] == ["public-verified"]


def test_a_half_configured_database_is_refused_before_anything_is_read(clean_tables, rls_subject):
    """The likeliest real misconfiguration after #436: the closures policy was
    applied in #434, the reports one was not, and half a baseline would look
    exactly like a day with no reports. The refusal names the table that is
    missing its policy."""
    clean_tables.execute("ALTER TABLE public.closures ENABLE ROW LEVEL SECURITY")
    clean_tables.execute("ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY")
    clean_tables.execute(
        f"""
        CREATE POLICY conditions_reader_closures ON public.closures
            FOR SELECT TO {READER} USING (moderation_status = 'verified')
        """
    )

    assert_reader_permissions(rls_subject, "closures")

    with pytest.raises(SystemExit) as exc:
        assert_reader_permissions(rls_subject, "reports")
    assert "public.reports" in str(exc.value)


@pytest.fixture
def published_to(tmp_path, monkeypatch):
    """Point the exporter's four artifacts and its manifest at a scratch
    directory, and hand back the directory they will land in."""
    out_dir = tmp_path / "conditions"
    out_dir.mkdir()
    monkeypatch.setattr(export_conditions, "OUT_DIR", out_dir)
    for name, filename in (
        ("CLOSURES_OUT_PATH", "closures.json"),
        ("REPORTS_OUT_PATH", "reports.json"),
        ("NOTES_OUT_PATH", "notes.json"),
        ("DISPUTES_OUT_PATH", "disputes.json"),
    ):
        monkeypatch.setattr(export_conditions, name, out_dir / filename)
    monkeypatch.setattr(export_conditions, "MANIFEST_PATH", tmp_path / "conditions_manifest.json")
    return out_dir


@pytest.fixture
def reading_as_the_reader(monkeypatch):
    """`main()` connects from the environment, so this is how a test makes it
    connect as the non-owner role RLS actually binds."""
    host = SCRATCH_URL.split("://", 1)[1].split("@", 1)[1]
    monkeypatch.setenv("CONDITIONS_DATABASE_URL", f"postgresql://{READER}:{READER_PASSWORD}@{host}")


def test_an_unconfigured_notes_table_still_publishes_the_safety_baseline(
    clean_tables, rls_subject, published_to, reading_as_the_reader
):
    """#922, end to end, and the whole point of the change.

    From 2026-08-20 to 2026-08-22 both environments had closures and reports
    fully configured and `field_notes` not configured at all, and the
    all-or-nothing pre-flight turned that into no bake whatsoever - the
    offline safety baseline ageing in the bucket for two days while the notes
    feature nobody had finished setting up held it hostage.

    So: the two configured artifacts publish, the two that would be lies are
    omitted, and the manifest carries exactly what was written."""
    clean_tables.execute(f"REVOKE SELECT ON public.field_notes FROM {READER}")
    _insert(clean_tables, closure_id="c1", moderation_status="verified")

    manifest = export_conditions.main()

    assert (published_to / "closures.json").exists()
    assert (published_to / "reports.json").exists()
    # Absent, not empty. A key that 404s falls back on the client; a document
    # holding `[]` is a claim that nobody has written a note about this trail.
    assert not (published_to / "notes.json").exists()
    assert not (published_to / "disputes.json").exists()
    assert set(manifest["artifacts"]) == {"closures", "reports"}

    published = json.loads((published_to / "closures.json").read_text())
    assert [row["id"] for row in published["closures"]] == ["c1"]


def test_a_notes_table_that_does_not_exist_yet_publishes_the_baseline_too(
    clean_tables, rls_subject, published_to, reading_as_the_reader
):
    """Production's signature specifically, which is not UA's.

    UA had run migration d7e2b9c41f68 and merely lacked the GRANT; production
    had never run it, so `field_notes` was not there at all and the check
    raised UndefinedTable out of psycopg before it could refuse politely. Both
    have to reach the same place, or fixing the one visible in the log leaves
    the other environment still red."""
    clean_tables.execute("DROP TABLE public.field_notes")
    try:
        _insert(clean_tables, closure_id="c1", moderation_status="verified")

        manifest = export_conditions.main()

        assert set(manifest["artifacts"]) == {"closures", "reports"}
        assert not (published_to / "notes.json").exists()
    finally:
        # Module-scoped table, so put it back for whatever runs next.
        clean_tables.execute(FIELD_NOTES_DDL)
        clean_tables.execute(f"GRANT SELECT ON public.field_notes TO {READER}")


def test_an_unconfigured_notes_table_says_so_where_a_run_summary_will_show_it(
    clean_tables, rls_subject, published_to, reading_as_the_reader, capsys
):
    """Omitting quietly is one of the two failure modes this replaces, so the
    skip has to be visible without opening the step log. `::warning::` is what
    the workflow's own missing-secret gate uses."""
    clean_tables.execute(f"REVOKE SELECT ON public.field_notes FROM {READER}")

    export_conditions.main()

    said = capsys.readouterr().out
    assert "::warning::" in said
    assert "field_notes" in said
    assert "d7e2b9c41f68" in said


def test_an_unconfigured_closures_table_still_stops_everything(clean_tables, rls_subject, reading_as_the_reader):
    """The other half, and the reason PENDING_READER_SETUP is a named set
    rather than "carry on regardless". Closures are configured in both
    environments today, so losing the grant is a regression - and a regression
    that published a partial baseline while going green would be exactly the
    quiet failure this file exists to prevent."""
    clean_tables.execute(f"REVOKE SELECT ON public.closures FROM {READER}")

    with pytest.raises(SystemExit) as exc:
        export_conditions.main()
    assert "public.closures" in str(exc.value)


def test_the_catalog_queries_answer_against_a_real_schema(clean_tables):
    """The three SQL constants, run for real against every table. A typo in
    one of them would otherwise only show up against production, where it
    fails open."""
    for table in ("closures", "reports", "field_notes"):
        with clean_tables.cursor() as cur:
            cur.execute(MAY_SELECT_SQL, (f"public.{table}",))
            assert cur.fetchone()[0] is True

            cur.execute(RLS_ENABLED_SQL, (f"public.{table}",))
            assert cur.fetchone()[0] is False

            cur.execute(POLICY_COUNT_SQL, (table,))
            assert cur.fetchone()[0] == 0

    with clean_tables.cursor() as cur:
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
            # The closure's two endpoints (#674) - the anchor the miles above
            # are a per-release projection of.
            "start_lat",
            "start_lon",
            "end_lat",
            "end_lon",
        ]

    with clean_tables.cursor() as cur:
        cur.execute(PUBLIC_REPORTS_SQL)
        assert [d.name for d in cur.description] == [
            "id",
            "type",
            "poi_id",
            "lat",
            "lon",
            "mile",
            "reporter_type",
            "timestamp",
            "note",
            "follow_up",
            "status",
            "visibility",
            "severity",
        ]


# --- The endpoint geometry reaches the baseline (#674) ----------------------
#
# The rollout-window fallback that used to sit here is gone: production ran
# b6e3f1a72d84 on 2026-08-19, so the reader and the schema agree again and a
# missing column is a real fault rather than an expected state. What stays is
# the assertion that the columns actually reach the artifact.


def test_the_migrated_database_publishes_the_geometry(clean_tables):
    clean_tables.execute(
        "INSERT INTO public.closures (id, reported_by, reported_at, start_mile_marker, "
        "end_mile_marker, reason_type, moderation_status, start_lat, start_lon, end_lat, end_lon) "
        "VALUES ('c1', 'p1', now(), 100.0, 102.0, 'storm_damage', 'verified', 40.9, -73.9, 41.1, -73.7)"
    )

    rows = export_conditions.read_closures(clean_tables)

    assert rows[0]["start_lat"] == 40.9
    assert rows[0]["end_lon"] == -73.7
