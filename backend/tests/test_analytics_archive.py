"""The usage archive: closed months' unlinked rows move to R2 as Parquet (#1923).

app/core/analytics_archive.py promises a row is always in exactly one place -
Postgres or one archived part - and that everything which read the rows before
they moved reads the same afterwards. Each test below is one of those
promises, against the real Postgres every backend test uses and S3 doubled
in-process with moto, the project's convention (tests/test_report_photos.py).
"""

import importlib.util
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import analytics_archive, analytics_quality, analytics_rollup, analytics_storage
from app.core.analytics_archive import ArchiveBusy, ArchiveError, R2Store, object_key
from app.core.analytics_rollup import ALL, retention_start
from app.models.analytics import (
    AnalyticsArchivedDaily,
    AnalyticsArchivePart,
    AnalyticsEvent,
    AnalyticsMonthly,
)

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "analytics_archive.py"
MIGRATION = BACKEND / "alembic" / "versions" / "8f6794da722d_usage_archive_tables.py"
BUCKET = "ourhike-usage-test"

OCTOBER = date(2026, 10, 1)
# The rollup closes October on 14 November (CLOSE_AFTER_DAYS); the archive
# takes a closed month on a later night.
CLOSED = date(2026, 11, 20)
ARCHIVE_DAY = date(2026, 11, 21)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load(SCRIPT, "analytics_archive_script")


@pytest.fixture()
def store():
    """The environment's bucket, doubled. An AWS-shaped endpoint, for the reason
    tests/test_report_photos.py's fixture gives: moto intercepts those only."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield R2Store(client, BUCKET)


def _event(db_session, day: date, *, received: date | None = None, **fields) -> AnalyticsEvent:
    event = AnalyticsEvent(
        id=fields.pop("id", str(uuid.uuid4())),
        local_date=day,
        received_on=received or day,
        event=fields.pop("event", "map_screen_viewed"),
        platform=fields.pop("platform", "android"),
        **fields,
    )
    db_session.add(event)
    db_session.commit()
    # Detached with its columns loaded, so a test can still read its id after
    # the archive has deleted the row it came from.
    db_session.refresh(event)
    db_session.expunge(event)
    return event


def _october(db_session) -> dict[str, list[str]]:
    """A month's worth of every kind of row: linked and not, every event, three
    platforms, two versions and none, sealed, no_key and unsealed."""
    ids: dict[str, list[str]] = {"linked": [], "unlinked": []}
    events = ["app_installed", "user_login", "hike_plan_made", "hike_plan_completed", "map_screen_viewed", "session"]
    for index in range(36):
        day = OCTOBER + timedelta(days=index % 28)
        linked = index % 4 == 0
        event = _event(
            db_session,
            day,
            received=day + timedelta(days=index % 3),
            event=events[index % len(events)],
            platform=("ios", "android", "web")[index % 3],
            app_version=("1.5.0", "1.6.0", None)[index % 3],
            user_key=f"k{index:031d}" if linked else None,
            week_first=index % 2 == 0,
            pageviews=index % 7 if events[index % len(events)] == "session" else None,
            seal=("sealed", "no_key", "none")[index % 3],
            sealed=bytes([index]) * 40 if index % 3 == 0 else None,
            clubs={"atc": 1.0} if index % 5 == 0 else None,
            area_lat=43.7 if index % 2 else None,
            area_lon=-72.3 if index % 2 else None,
        )
        ids["linked" if linked else "unlinked"].append(event.id)
    return ids


def _close_october(db_session) -> None:
    analytics_rollup.run(db_session, today=CLOSED)


def _archive(db_session, store, script, today: date = ARCHIVE_DAY):
    return analytics_archive.run(db_session, store, script.write_parquet, today=today)


def _held_ids(db_session) -> set[str]:
    return {row[0] for row in db_session.execute(text("select id from analytics_events"))}


def _part_rows(store, script, month: date, part: int) -> list[dict]:
    return script.read_parquet(store.get(object_key(month, part)))


# --- what moves, and what does not ---------------------------------------------


def test_a_closed_months_unlinked_rows_move_to_one_part_and_leave_postgres(db_session, store, script):
    ids = _october(db_session)
    _close_october(db_session)

    result = _archive(db_session, store, script)

    assert result.archived == [(OCTOBER, 1)]
    archived = _part_rows(store, script, OCTOBER, 1)
    assert {row["id"] for row in archived} == set(ids["unlinked"])
    assert _held_ids(db_session) == set(ids["linked"])
    part = db_session.get(AnalyticsArchivePart, (OCTOBER, 1))
    assert part.rows == len(ids["unlinked"])
    assert part.object_key == "2026-10/part-0001.parquet"
    assert part.bytes == len(store.get(part.object_key))


def test_linked_rows_and_months_still_open_never_move(db_session, store, script):
    """Linked rows stay to their six months, so deletion and unlinking never
    rewrite a file; a month that has not closed is not archived at all."""
    linked = _event(db_session, date(2026, 10, 5), user_key="k" * 32)
    november = _event(db_session, date(2026, 11, 3))
    _close_october(db_session)

    assert _archive(db_session, store, script).archived == []
    assert _held_ids(db_session) == {linked.id, november.id}
    assert store.keys() == []


def test_the_file_is_sorted_by_date_event_and_platform_not_by_arrival(db_session, store, script):
    """Arrival order is what grouped a batch's rows through `xmin` (#1903's review)."""
    _october(db_session)
    _close_october(db_session)
    _archive(db_session, store, script)

    rows = _part_rows(store, script, OCTOBER, 1)
    keys = [(row["local_date"], row["event"], row["platform"], row["id"]) for row in rows]
    assert keys == sorted(keys)


def test_the_file_keeps_every_column_typed_and_the_sealed_blob_whole(db_session, store, script):
    sealed = bytes(range(64))
    row = _event(
        db_session,
        date(2026, 10, 9),
        event="session",
        pageviews=4,
        session_length="m1_to_5",
        clubs={"atc": 0.75, "gmc": 0.25},
        club_firsts=["gmc"],
        area_lat=44.2,
        area_lon=-71.3,
        has_fix=True,
        seal="sealed",
        sealed=sealed,
    )
    _close_october(db_session)
    _archive(db_session, store, script)

    body = store.get(object_key(OCTOBER, 1))
    assert set(script.read_parquet(body)[0]) == {column.name for column in AnalyticsEvent.__table__.columns}
    (archived,) = script.read_parquet(body)
    assert archived["id"] == row.id
    assert archived["event"] == "session" and archived["session_length"] == "m1_to_5"
    assert archived["sealed"] == sealed
    assert archived["clubs"] == '{"atc":0.75,"gmc":0.25}'
    assert archived["club_firsts"] == '["gmc"]'
    assert float(archived["area_lat"]) == 44.2 and float(archived["area_lon"]) == -71.3
    assert archived["user_key"] is None


# --- a row in exactly one place ------------------------------------------------


def test_a_failed_upload_deletes_nothing_and_records_nothing(db_session, store, script, monkeypatch):
    ids = _october(db_session)
    _close_october(db_session)

    def refuse(key, body):
        raise ConnectionError("R2 is down")

    monkeypatch.setattr(store, "put", refuse)
    with pytest.raises(ConnectionError):
        _archive(db_session, store, script)

    assert _held_ids(db_session) == set(ids["linked"]) | set(ids["unlinked"])
    assert db_session.query(AnalyticsArchivePart).count() == 0
    assert db_session.query(AnalyticsArchivedDaily).count() == 0


def test_a_run_that_dies_after_the_upload_writes_the_same_part_again(db_session, store, script, monkeypatch):
    """The file is in R2 with no ledger row; the next run numbers its part from
    the ledger, writes part 1 again over it, and no row is in two files."""
    ids = _october(db_session)
    _close_october(db_session)
    real_record = analytics_archive.record

    def die(*args, **kwargs):
        raise RuntimeError("the runner went away")

    monkeypatch.setattr(analytics_archive, "record", die)
    with pytest.raises(RuntimeError):
        _archive(db_session, store, script)
    assert store.keys() == ["2026-10/part-0001.parquet"]
    assert _held_ids(db_session) == set(ids["linked"]) | set(ids["unlinked"])

    late = _event(db_session, date(2026, 10, 30), received=ARCHIVE_DAY)
    monkeypatch.setattr(analytics_archive, "record", real_record)
    assert _archive(db_session, store, script).archived == [(OCTOBER, 1)]

    assert store.keys() == ["2026-10/part-0001.parquet"]
    archived = [row["id"] for row in _part_rows(store, script, OCTOBER, 1)]
    assert sorted(archived) == sorted([*ids["unlinked"], late.id])
    assert _held_ids(db_session) == set(ids["linked"])


def test_rows_are_deleted_by_id_so_a_row_that_arrives_mid_archive_stays(db_session, store, script, monkeypatch):
    """Deleting by "October, no user_key" would delete a late row that arrived
    between the read and the delete without its ever reaching a file."""
    ids = _october(db_session)
    _close_october(db_session)
    arrived: list[str] = []

    def write_then_a_row_arrives(batches):
        body = script.write_parquet(batches)
        with Session(db_session.bind) as other:
            row = AnalyticsEvent(
                id=str(uuid.uuid4()), local_date=date(2026, 10, 31), received_on=ARCHIVE_DAY, event="session", platform="web"
            )
            other.add(row)
            other.commit()
            arrived.append(row.id)
        return body

    analytics_archive.run(db_session, store, write_then_a_row_arrives, today=ARCHIVE_DAY)

    assert _held_ids(db_session) == set(ids["linked"]) | set(arrived)
    assert arrived[0] not in {row["id"] for row in _part_rows(store, script, OCTOBER, 1)}


def test_rows_arriving_after_the_first_part_go_into_part_two(db_session, store, script):
    _october(db_session)
    _close_october(db_session)
    _archive(db_session, store, script)
    late = _event(db_session, date(2026, 10, 28), received=date(2026, 11, 25))

    assert _archive(db_session, store, script, today=date(2026, 11, 26)).archived == [(OCTOBER, 2)]
    assert [row["id"] for row in _part_rows(store, script, OCTOBER, 2)] == [late.id]


def test_a_row_unlinked_after_the_close_is_archived_on_a_later_pass(db_session, store, script):
    """`forget_link` takes the code off a hiker's rows (app/core/analytics_accounts.py);
    such a row stops being linked, and the next pass archives it."""
    row = _event(db_session, date(2026, 10, 12), user_key="k" * 32, seal="sealed", sealed=b"\x01" * 40)
    _close_october(db_session)
    assert _archive(db_session, store, script).archived == []

    db_session.execute(
        text("update analytics_events set user_key = null, seal = 'unlinked', sealed = null where id = :id"),
        {"id": row.id},
    )
    db_session.commit()

    assert _archive(db_session, store, script, today=date(2026, 11, 22)).archived == [(OCTOBER, 1)]
    (archived,) = _part_rows(store, script, OCTOBER, 1)
    assert archived["id"] == row.id and archived["sealed"] is None


def test_a_run_stops_when_another_holds_the_lock(db_session, store, script):
    _october(db_session)
    _close_october(db_session)
    with db_session.bind.connect() as other:
        other.execute(text("select pg_advisory_xact_lock(hashtext('analytics-archive'))"))
        with pytest.raises(ArchiveBusy):
            _archive(db_session, store, script)
        other.rollback()
    assert store.keys() == []


# --- what read the rows before reads the same after -----------------------------


def _series(db_session, today: date):
    arrivals = analytics_quality.load_arrivals(db_session, today)
    platforms = analytics_quality.load_platform_arrivals(db_session, today)
    window = {"start": today - timedelta(days=60), "end": today}
    versions = sorted(
        tuple(sorted(dict(row).items())) for row in db_session.execute(analytics_quality._BY_VERSION, window).mappings()
    )
    no_key = db_session.execute(analytics_quality._NO_KEY, {"start": OCTOBER}).scalar_one()
    daily = {
        (metric, day, age): arrivals.at(metric, day, age)
        for metric in analytics_quality.DAILY_METRICS
        for day in (OCTOBER + timedelta(days=offset) for offset in range(31))
        for age in (0, 1, 2, 30)
    }
    by_platform = {
        (platform, metric, day): platforms[platform].at(metric, day, 30)
        for platform in analytics_quality.PLATFORMS
        for metric in analytics_quality.PLATFORM_METRICS
        for day in (OCTOBER + timedelta(days=offset) for offset in range(31))
    }
    return daily, by_platform, versions, no_key


def test_the_checks_series_read_the_same_before_and_after_the_rows_move(db_session, store, script):
    """The maintainer's choice (poll, 2026-10-29): readers stay on Postgres. They
    read rows still held plus the archived daily counts, and see no seam."""
    _october(db_session)
    _close_october(db_session)
    before = _series(db_session, ARCHIVE_DAY)
    assert any(before[0].values()), "the fixture counts nothing, so the comparison proves nothing"

    _archive(db_session, store, script)
    assert db_session.query(AnalyticsArchivedDaily).count() > 0

    assert _series(db_session, ARCHIVE_DAY) == before


def test_a_second_part_adds_to_the_same_days_counts(db_session, store, script):
    _october(db_session)
    _close_october(db_session)
    _archive(db_session, store, script)
    _event(db_session, date(2026, 10, 3), received=date(2026, 10, 3), event="session", pageviews=9)
    before = _series(db_session, date(2026, 11, 26))

    _archive(db_session, store, script, today=date(2026, 11, 26))

    assert _series(db_session, date(2026, 11, 26)) == before


def test_the_rollup_counts_archived_rows_back_into_a_closed_months_late_rows(db_session, store, script):
    _october(db_session)
    _close_october(db_session)
    _archive(db_session, store, script)
    _event(db_session, date(2026, 10, 30), received=date(2026, 11, 25))

    analytics_rollup.run(db_session, today=date(2026, 11, 26))

    late = db_session.get(AnalyticsMonthly, (OCTOBER, "events_after_close", ALL, ALL))
    assert late.value == 1


def test_rows_held_come_down_once_the_archive_has_run_before_the_rollup(db_session, store, script):
    """The intake ceiling counts the rollup's nightly snapshot, so what moved
    stops counting against it the same night (analytics-rollup.yml runs the
    archive first)."""
    ids = _october(db_session)
    _close_october(db_session)
    before = analytics_storage.rows_held(db_session)

    _archive(db_session, store, script)
    analytics_rollup.run(db_session, today=ARCHIVE_DAY)

    assert analytics_storage.rows_held(db_session) == before - len(ids["unlinked"])


# --- retention -------------------------------------------------------------------


def test_past_retention_every_file_goes_with_its_ledger_and_counts(db_session, store, script):
    """Every file under an expired month's prefix - a part a dead run left
    behind included, which the ledger never held."""
    _october(db_session)
    _close_october(db_session)
    _archive(db_session, store, script)
    store.put("2026-10/part-0007.parquet", b"left by a run that died")
    later = date(2027, 5, 2)
    assert retention_start(later) > OCTOBER

    result = _archive(db_session, store, script, today=later)

    assert result.retired == [OCTOBER]
    assert store.keys() == []
    assert db_session.get(AnalyticsArchivePart, (OCTOBER, 1)).deleted_at is not None
    assert db_session.query(AnalyticsArchivedDaily).count() == 0


def test_a_month_inside_retention_keeps_its_files(db_session, store, script):
    _october(db_session)
    _close_october(db_session)
    _archive(db_session, store, script)

    result = _archive(db_session, store, script, today=date(2027, 4, 30))

    assert result.retired == []
    assert store.keys() == ["2026-10/part-0001.parquet"]


# --- the command ----------------------------------------------------------------


@pytest.fixture()
def command(script, db_session, store, monkeypatch):
    @contextmanager
    def session():
        yield db_session

    monkeypatch.setattr(script, "SessionLocal", session)
    monkeypatch.setattr(script.R2Store, "from_env", classmethod(lambda cls: store))
    return script


def test_the_command_names_months_and_parts_and_never_a_count(db_session, command, capsys):
    """Dated from the real day, which the command refuses to run ahead of."""
    today = datetime.now().date()
    month = analytics_rollup.add_months(analytics_rollup.month_start(today), -2)
    unlinked = [_event(db_session, month + timedelta(days=day)).id for day in range(13)]
    analytics_rollup.run(db_session, today=today)

    assert command.main([]) == 0

    out = capsys.readouterr().out
    assert f"Archived {month:%Y-%m} as part 1" in out
    assert str(len(unlinked)) not in out.replace(f"{month:%Y-%m}", "").replace("part 1", "")


def test_the_command_refuses_a_date_after_today(command, capsys):
    tomorrow = datetime.now().date() + timedelta(days=2)
    assert command.main(["--today", tomorrow.isoformat()]) == 2
    assert "Nothing was run" in capsys.readouterr().err


def test_the_command_says_which_settings_are_missing_and_archives_nothing(script, monkeypatch, capsys):
    for name in analytics_archive.ENV.values():
        monkeypatch.delenv(name, raising=False)
    assert script.main([]) == 1
    err = capsys.readouterr().err
    assert "USAGE_ARCHIVE_R2_BUCKET" in err and "not configured" in err


# --- the migration ----------------------------------------------------------------


def test_the_migrations_grant_runs_for_an_existing_role_and_skips_a_missing_one(db_session):
    """The rollup's role needs SELECT and a policy on both tables, or the night
    this deploys `_count_late` fails with "permission denied". Run here against
    the test user, which exists, and against a role that does not."""
    migration = _load(MIGRATION, "usage_archive_migration")
    me = db_session.execute(text("select current_user")).scalar_one()
    for role in (me, "ourhike_no_such_role"):
        for statement in migration.grant_statements("postgresql", role=role):
            db_session.execute(text(statement))
    policies = db_session.execute(
        text(
            "select tablename, policyname from pg_policies where tablename in ('analytics_archive_parts', 'analytics_archived_daily')"
        )
    ).all()
    db_session.rollback()
    assert sorted(policies) == [
        ("analytics_archive_parts", "rollup_archive_parts"),
        ("analytics_archived_daily", "rollup_archived_daily"),
    ]
    assert migration.grant_statements("sqlite") == []


def test_an_archive_error_message_carries_no_figure():
    """The archive's messages reach a public Actions log."""
    error = ArchiveError(f"{object_key(OCTOBER, 1)}: fewer rows were deleted than the file holds")
    assert not any(character.isdigit() for character in str(error).replace("2026-10/part-0001", ""))
