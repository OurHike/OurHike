"""The roles' SQL in features/EVENTING.md §0 is enough for each role's night (#1923).

The maintainer runs that SQL by hand in each environment's database, so a
grant it lacks is first found by a nightly run that fails on it. This runs
the two blocks exactly as written there, then a night as each role against
them: the rollup closing a month, the archive moving it, and the rollup and
the checks reading it back the night after. It also holds the archive role's
one privacy property, the reason it is a role of its own: it reads `sealed`,
but cannot see a row an account is linked to.

It needs a database user that may create roles and become them. CI's
Postgres service user is a superuser (backend-tests.yml); the one
scripts/local-postgres.sh makes is not, so it skips there and says so. Roles
belong to the whole server rather than to the test's database, so everything
happens inside one transaction that is rolled back: no role outlives the
test, and a parallel worker running it at the same moment waits on the
first one's role rather than colliding with it.
"""

import importlib.util
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core import analytics_archive, analytics_quality, analytics_rollup
from app.core.analytics_archive import R2Store
from app.core.analytics_rollup import ALL
from app.models.analytics import AnalyticsEvent, AnalyticsMonth, AnalyticsMonthly, MonthStatus

EVENTING = Path(__file__).resolve().parents[2] / "features" / "EVENTING.md"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analytics_archive.py"

OCTOBER = date(2026, 10, 1)
CLOSED = date(2026, 11, 20)
ARCHIVE_DAY = date(2026, 11, 21)


def _role_sql(heading: str) -> str:
    """The first SQL block under `### <heading>` in EVENTING.md, with a password in place of its placeholder."""
    section = EVENTING.read_text(encoding="utf-8").split(f"\n### {heading}\n", 1)[1]
    block = re.search(r"```sql\n(.*?)```", section, re.DOTALL)
    assert block is not None, f"EVENTING.md's {heading!r} section has no SQL block"
    assert "'<generated>'" in block.group(1)
    return block.group(1).replace("'<generated>'", "'only-inside-a-rolled-back-test'")


@pytest.fixture()
def connection(db_engine):
    """One connection inside a transaction the test never commits, with both roles made as EVENTING.md says."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            if not connection.execute(text("select rolsuper from pg_roles where rolname = current_user")).scalar_one():
                pytest.skip(
                    "needs a database user that may create roles and become them, as CI's is; "
                    "scripts/local-postgres.sh's is not (this module's docstring)"
                )
            # Every usage table is locked with no policies in a migrated database
            # (897b71ad5fff, 8f6794da722d); create_all, which these tests use, does not.
            for (table,) in connection.execute(
                text("select tablename from pg_tables where schemaname = 'public' and tablename like 'analytics\\_%'")
            ):
                connection.exec_driver_sql(f"alter table public.{table} enable row level security")
            connection.exec_driver_sql(_role_sql("The rollup's role"))
            connection.exec_driver_sql(_role_sql("The archive's role"))
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture()
def store():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="ourhike-usage-test")
        yield R2Store(client, "ourhike-usage-test")


@pytest.fixture(scope="module")
def write_parquet():
    spec = importlib.util.spec_from_file_location("analytics_archive_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.write_parquet


def _become(connection, role: str | None) -> None:
    """Act as `role` from here to the end of the test's transaction; None is the owner again."""
    connection.exec_driver_sql("reset role")
    if role is not None:
        connection.exec_driver_sql(f"set local role {role}")


def _as(connection, role: str | None) -> Session:
    """A session acting as `role`, whose commits stay inside the test's transaction.

    The role is set on the connection before the session opens its first
    savepoint, so a session's own rollback cannot undo it.
    """
    _become(connection, role)
    return Session(bind=connection, join_transaction_mode="create_savepoint")


def _october(connection) -> dict[str, set[str]]:
    """Unlinked and linked rows across October, sealed and not, added as the owner - as the route would."""
    ids: dict[str, set[str]] = {"linked": set(), "unlinked": set()}
    with _as(connection, None) as db:
        for index in range(12):
            linked = index % 3 == 0
            event = AnalyticsEvent(
                id=str(uuid.uuid4()),
                local_date=OCTOBER + timedelta(days=index * 2),
                received_on=OCTOBER + timedelta(days=index * 2 + index % 2),
                event=("session", "map_screen_viewed", "hike_plan_made")[index % 3],
                platform=("ios", "android", "web")[index % 3],
                app_version="1.6.0",
                user_key=f"k{index:031d}" if linked else None,
                week_first=index % 2 == 0,
                pageviews=3 if index % 3 == 0 else None,
                seal="sealed" if index % 2 else "none",
                sealed=bytes([index]) * 40 if index % 2 else None,
            )
            db.add(event)
            ids["linked" if linked else "unlinked"].add(event.id)
        db.commit()
    return ids


def _denied(connection, statement: str) -> bool:
    """Whether the current role is refused `statement`, without spoiling the test's transaction."""
    try:
        with connection.begin_nested():
            connection.exec_driver_sql(statement)
    except ProgrammingError as refusal:
        return "permission denied" in str(refusal)
    return False


def test_each_role_runs_its_night_on_exactly_the_grants_eventing_md_gives(connection, store, write_parquet):
    ids = _october(connection)

    with _as(connection, "ourhike_analytics_rollup") as db:
        analytics_rollup.run(db, today=CLOSED)
        assert db.get(AnalyticsMonth, OCTOBER).status == MonthStatus.closed

    with _as(connection, "ourhike_analytics_archive") as db:
        result = analytics_archive.run(db, store, write_parquet, today=ARCHIVE_DAY)
    assert result.archived == [(OCTOBER, 1)]

    with _as(connection, None) as db:
        held = {row[0] for row in db.execute(text("select id from analytics_events"))}
        late = AnalyticsEvent(id=str(uuid.uuid4()), local_date=OCTOBER, received_on=ARCHIVE_DAY, event="session", platform="web")
        db.add(late)
        db.commit()
    assert held == ids["linked"]

    # The night after, as the rollup: it reads the archive's ledger for October's
    # late rows and the daily counts for the checks, and still not `sealed`.
    with _as(connection, "ourhike_analytics_rollup") as db:
        analytics_rollup.run(db, today=ARCHIVE_DAY + timedelta(days=1))
        analytics_quality.run_checks(db, today=ARCHIVE_DAY + timedelta(days=1))
    assert _denied(connection, "select sealed from public.analytics_events")

    with _as(connection, None) as db:
        late = db.get(AnalyticsMonthly, (OCTOBER, "events_after_close", ALL, ALL))
    assert late.value == 1, "the archived rows were added back, so only the one late row counts"


def test_the_archive_role_cannot_see_or_delete_a_linked_row(connection):
    ids = _october(connection)

    with _as(connection, "ourhike_analytics_archive") as db:
        seen = {row[0] for row in db.execute(text("select id from analytics_events"))}
        deleted = db.execute(text("delete from analytics_events where user_key is not null")).rowcount
        db.commit()

    assert seen == ids["unlinked"]
    assert deleted == 0
    with _as(connection, None) as db:
        assert {row[0] for row in db.execute(text("select id from analytics_events where user_key is not null"))} == (
            ids["linked"]
        )


@pytest.mark.parametrize(
    "statement",
    [
        "select 1 from public.analytics_users",
        "select 1 from public.analytics_seal_keys",
        "select 1 from public.analytics_monthly",
        "update public.analytics_months set computed_at = computed_at",
        "insert into public.analytics_events (id) values ('x')",
    ],
)
def test_the_archive_role_reaches_nothing_else(connection, statement):
    _become(connection, "ourhike_analytics_archive")

    assert _denied(connection, statement)
