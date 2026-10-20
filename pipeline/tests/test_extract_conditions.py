"""extract/_kinds.py's conditions_query against a real Postgres: OurHike's own closures, reports, notes and disputes.

The rows are the bake's own (export_conditions.py's PUBLIC_*_SQL, run
unchanged), so these tests are about what the extract adds around them. The
proof is the query's own count. Person columns never land. A table the reader
cannot see stops the lane, except `field_notes`, which PENDING_READER_SETUP
leaves out without stopping closures. A table that becomes unavailable is
withdrawn from the warehouse, never served from its last load.

Each xdist worker gets its own scratch database, so the DROP DATABASE in one
cannot pull a table out from under another. The suite skips where no
Postgres answers; CI's pytest job runs one (pipeline-tests.yml).
"""

import os

import psycopg
import pytest

from extract import _kinds
from extract._kinds import ConditionsQuery
from tests.test_export_conditions import (
    ADMIN_URL,
    CLOSURES_DDL,
    FIELD_NOTES_DDL,
    REPORTS_DDL,
    _insert,
    _insert_note,
    _insert_report,
)
from tests.test_extract_run import lane, warehouse

SCRATCH_DB = f"ourhike_extract_conditions_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}"
SCRATCH_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{SCRATCH_DB}"


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


@pytest.fixture
def conditions(monkeypatch):
    """A fresh scratch database holding closures and reports, and field_notes unless a test drops it."""
    try:
        with psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")
            admin.execute(f"CREATE DATABASE {SCRATCH_DB}")
    except psycopg.OperationalError as exc:
        pytest.skip(f"no Postgres to test against ({exc.__class__.__name__}) - run backend/scripts/local-postgres.sh")
    monkeypatch.setenv("CONDITIONS_DATABASE_URL", SCRATCH_URL)
    with psycopg.connect(SCRATCH_URL, autocommit=True) as conn:
        for ddl in (CLOSURES_DDL, REPORTS_DDL, FIELD_NOTES_DDL):
            conn.execute(ddl)
        yield conn
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB}")


def ourhike(key, type_):
    return ConditionsQuery(key=key, club="ourhike", type=type_)


def columns(con, table):
    return {row[0]: row[1] for row in con.execute(f'describe raw."{table}"').fetchall()}


def test_only_verified_closures_land_and_they_name_nobody(conditions, store):
    _insert(conditions, closure_id="yes", moderation_status="verified")
    _insert(conditions, closure_id="no", moderation_status="submitted", mile=20.0)

    report = lane(store, ourhike("closures", "closures"))

    assert report.rows["raw_ourhike__closures"] == 1 and report.proofs["raw_ourhike__closures"] == 1
    con, _ = warehouse(store)
    assert con.execute('select id from raw."raw_ourhike__closures"').fetchall() == [("yes",)]
    landed = columns(con, "raw_ourhike__closures")
    assert not {"reported_by", "verified_by"} & set(landed), "the query withholds them, and so does the raw store"
    assert landed["start_mile_marker"] == "DOUBLE" and landed["verified_at"].startswith("TIMESTAMP")


def test_public_reports_land_with_verified_at_and_without_the_reporter(conditions, store):
    _insert_report(conditions, report_id="public")
    _insert_report(conditions, report_id="private", visibility="private")
    _insert_report(conditions, report_id="pending", status="submitted")

    lane(store, ourhike("reports", "warnings"))

    con, counts = warehouse(store)
    assert counts["raw_ourhike__reports"] == 1
    landed = columns(con, "raw_ourhike__reports")
    assert "verified_at" in landed
    assert not {"reporter_id", "verified_by", "maintainer_id", "received_at", "photo_url"} & set(landed)


def test_a_week_with_no_dispute_lands_an_empty_table_with_the_querys_own_computed_columns(conditions, store):
    _insert_note(conditions, note_id="n1", observation="not_found")  # one account is not a dispute

    report = lane(store, ourhike("disputes", "warnings"))

    assert report.outcome == "loaded" and report.proofs["raw_ourhike__disputes"] == 0
    con, counts = warehouse(store)
    assert counts["raw_ourhike__disputes"] == 0
    landed = columns(con, "raw_ourhike__disputes")
    assert set(landed) >= {"poi_id", "accounts", "latest_at", "maintainer_said"}, "dlt's sql_table reflection missed all three"
    assert landed["accounts"] == "BIGINT" and landed["maintainer_said"] == "BOOLEAN"


def test_an_unconfigured_field_notes_leaves_notes_out_and_closures_carry_on(conditions, store):
    conditions.execute("DROP TABLE public.field_notes")
    _insert(conditions, closure_id="yes", moderation_status="verified")

    report = lane(store, ourhike("closures", "closures"), ourhike("notes", "warnings"), ourhike("disputes", "warnings"))

    assert report.verdicts["raw_ourhike__notes"] == report.verdicts["raw_ourhike__disputes"] == "unavailable"
    assert "field_notes does not exist" in report.unavailable["raw_ourhike__notes"]
    assert report.rows == {"raw_ourhike__closures": 1}
    con, counts = warehouse(store)
    assert counts == {"raw_ourhike__closures": 1}, "absent, which the bake reads as unknown, never as no notes"
    logged = con.execute("select table_name, outcome from raw._extract_runs order by table_name").fetchall()
    assert logged == [
        ("raw_ourhike__closures", "loaded"),
        ("raw_ourhike__disputes", "unavailable"),
        ("raw_ourhike__notes", "unavailable"),
    ]


def test_notes_that_become_unavailable_are_withdrawn_rather_than_served_from_their_last_load(conditions, store):
    _insert_note(conditions, note_id="n1")
    lane(store, ourhike("notes", "warnings"))
    _, counts = warehouse(store)
    assert counts["raw_ourhike__notes"] == 1

    conditions.execute("DROP TABLE public.field_notes")
    lane(store, ourhike("notes", "warnings"))

    con, counts = warehouse(store)
    assert "raw_ourhike__notes" not in counts
    assert not con.execute("select * from duckdb_tables() where table_name = 'raw_ourhike__notes'").fetchall()


def test_a_closures_table_the_reader_cannot_see_stops_the_lane(conditions, store):
    conditions.execute("DROP TABLE public.closures")
    with pytest.raises(RuntimeError, match="public.closures does not exist"):
        lane(store, ourhike("closures", "closures"), ourhike("reports", "warnings"))


def test_a_query_that_starts_selecting_a_person_column_refuses_the_read(conditions, monkeypatch):
    _insert(conditions, closure_id="yes", moderation_status="verified")
    monkeypatch.setitem(_kinds.CONDITIONS_QUERIES, "closures", ("closures", "SELECT id, verified_by FROM public.closures"))
    with pytest.raises(RuntimeError, match="verified_by"):
        list(ourhike("closures", "closures").rows({}))
