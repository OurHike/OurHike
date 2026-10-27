"""usage measurement tables

Revision ID: 897b71ad5fff
Revises: b4d8e1f7a263
Create Date: 2026-10-27 00:48:19.362691

#1902 - Count six usage events with a sealed account id and GPS fix, keep
them six months, close each month into a table, and report them per club.
Eight tables, all new, nothing existing touched:

- `analytics_events`, the raw rows `POST /usage-events` writes, deleted by the
  nightly rollup six months on. The account id and the exact fix live only in
  `sealed`, which the backend can write and cannot read
  (app/core/analytics_seal.py).
- `analytics_months` and `analytics_monthly`, each month's lifecycle and its
  exact figures - exact because the fewer-than-25 mask is applied when a
  report is built, not here (the maintainer, poll 2026-10-27).
- `analytics_users`, the User table: lifetime figures for hikers who said yes
  to linking their account. No location column, deliberately
  (app/models/analytics.py).
- `analytics_seal_keys`, the public half of each month's sealing key, and
  `analytics_openings`, the record each use of the secret writes first.
- `analytics_intake`, how many rows arrived each day by app version and by
  what became of them - the only trace of a row the server refused - and
  `analytics_anomalies`, every finding of the nightly data-quality checks
  (app/core/analytics_quality.py).

A plain table with a date index rather than one partition per month, which
the strategy page drew: a month's rows go in one guarded DELETE
(app/core/analytics_rollup.py), and at the volumes EVENTING.md estimates that
is cheap, while partitions would need creating ahead of every month and would
have to be taught to the test harness and the drift check. Reasoned, not
measured; a month that DELETE is slow for is the evidence that would reverse it.

RLS: all eight join the union tests/test_migration_rls.py checks. Every one
of them is either a hiker's own measurement, the means to open it, or counts
describing it, and PostgREST would otherwise serve them to anyone holding the
anon key.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "897b71ad5fff"
down_revision: Union[str, Sequence[str], None] = "b4d8e1f7a263"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism and
# tests/test_migration_rls.py for the guard that unions these lists.
RLS_TABLES: tuple[str, ...] = (
    "analytics_events",
    "analytics_months",
    "analytics_monthly",
    "analytics_users",
    "analytics_seal_keys",
    "analytics_openings",
    "analytics_intake",
    "analytics_anomalies",
)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the eight tables, and lock them before anything can reach them."""
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column(
            "event",
            sa.Enum(
                "app_installed",
                "user_login",
                "hike_plan_made",
                "hike_plan_completed",
                "map_screen_viewed",
                "session",
                name="usageevent",
                native_enum=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column(
            "platform", sa.Enum("ios", "android", "web", name="usageplatform", native_enum=False, length=8), nullable=False
        ),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("user_key", sa.String(length=32), nullable=True),
        sa.Column("week_first", sa.Boolean(), nullable=False),
        sa.Column("month_first", sa.Boolean(), nullable=False),
        sa.Column("ever_first", sa.Boolean(), nullable=False),
        sa.Column("club_firsts", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("kind_month_first", sa.Boolean(), nullable=False),
        sa.Column("month_returning", sa.Boolean(), nullable=False),
        sa.Column("signed_in", sa.Boolean(), nullable=False),
        sa.Column("clubs", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("miles", sa.Float(), nullable=True),
        sa.Column("pageviews", sa.SmallInteger(), nullable=True),
        sa.Column(
            "session_length",
            sa.Enum("under_1m", "m1_to_5", "m5_to_20", "over_20m", name="sessionlength", native_enum=False, length=10),
            nullable=True,
        ),
        sa.Column("has_fix", sa.Boolean(), nullable=False),
        sa.Column("area_lat", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("area_lon", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column(
            "seal", sa.Enum("none", "sealed", "no_key", "unlinked", name="sealstate", native_enum=False, length=8), nullable=False
        ),
        sa.Column("sealed", sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analytics_events_local_date"), "analytics_events", ["local_date"], unique=False)
    op.create_index(op.f("ix_analytics_events_user_key"), "analytics_events", ["user_key"], unique=False)
    op.create_table(
        "analytics_anomalies",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("check_name", sa.String(length=48), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("observed", sa.Float(), nullable=True),
        sa.Column("expected", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("first_seen_on", sa.Date(), nullable=False),
        sa.Column("last_seen_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("day", "check_name", "scope"),
    )
    op.create_table(
        "analytics_intake",
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("app_version", sa.String(length=40), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(
                "stored",
                "duplicate",
                "invalid",
                "too_old",
                "future",
                "over_budget",
                "paused",
                "declined",
                "dropped_full",
                "dropped_refused",
                "held",
                name="intakeoutcome",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("received_on", "app_version", "outcome"),
    )
    op.create_table(
        "analytics_monthly",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(length=40), nullable=False),
        sa.Column("club", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=8), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("month", "metric", "club", "platform"),
    )
    op.create_table(
        "analytics_months",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("provisional", "closed", name="monthstatus", native_enum=False, length=12), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("raw_deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("month"),
    )
    op.create_table(
        "analytics_openings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("opened_by", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("selector", sa.String(length=120), nullable=False),
        sa.Column("rows_opened", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "analytics_seal_keys",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("month"),
    )
    op.create_table(
        "analytics_users",
        sa.Column("user_key", sa.String(length=32), nullable=False),
        sa.Column("first_seen_on", sa.Date(), nullable=False),
        sa.Column("new_month", sa.Date(), nullable=False),
        sa.Column("last_seen_on", sa.Date(), nullable=False),
        sa.Column(
            "first_platform", sa.Enum("ios", "android", "web", name="usageplatform", native_enum=False, length=8), nullable=False
        ),
        sa.Column(
            "last_platform", sa.Enum("ios", "android", "web", name="usageplatform", native_enum=False, length=8), nullable=False
        ),
        sa.Column("first_login_on", sa.Date(), nullable=True),
        sa.Column("first_plan_on", sa.Date(), nullable=True),
        sa.Column("first_completion_on", sa.Date(), nullable=True),
        sa.Column("logins", sa.Integer(), nullable=False),
        sa.Column("plans_made", sa.Integer(), nullable=False),
        sa.Column("plans_completed", sa.Integer(), nullable=False),
        sa.Column("plan_miles", sa.Float(), nullable=False),
        sa.Column("completed_miles", sa.Float(), nullable=False),
        sa.Column("map_views", sa.Integer(), nullable=False),
        sa.Column("sessions", sa.Integer(), nullable=False),
        sa.Column("pageviews", sa.Integer(), nullable=False),
        sa.Column("active_months", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("updated_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("user_key"),
    )

    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the eight tables; the locks go with them."""
    op.drop_table("analytics_intake")
    op.drop_table("analytics_anomalies")
    op.drop_table("analytics_users")
    op.drop_table("analytics_seal_keys")
    op.drop_table("analytics_openings")
    op.drop_table("analytics_months")
    op.drop_table("analytics_monthly")
    op.drop_index(op.f("ix_analytics_events_user_key"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_local_date"), table_name="analytics_events")
    op.drop_table("analytics_events")
