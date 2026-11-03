"""Two column conventions this repository follows and never wrote down.

Both were followed everywhere, by everyone, for a year - and both were
broken by the first models written without reading an older one, which is
the definition of a convention that needs a test rather than a habit.

**ENUM COLUMNS ARE VARCHAR WITH A CHECK, never a native Postgres type.**

This is a convention the repository has followed since `0f79a37f9358`, its
initial schema, and it was followed everywhere without being written down -
so the first model written without reading an older one broke it, which is
the definition of a convention that needs a test rather than a habit.

**WHAT BREAKING IT COSTS, measured 2026-09-17.** `app/models/mail.py` and
`app/models/nomination.py` were first written with SQLAlchemy's default
`Enum(...)`, which creates six native Postgres types. Postgres does not drop
a type when the last table using it is dropped, and Alembic's autogenerate
does not emit the `DROP TYPE`, so the revision's `downgrade` succeeded and
the next `upgrade` failed on `type "suppressionreason" already exists`. The
revision was irreversible in practice, and nothing said so until it was run
twice against the same database.

**AND ADDING A VALUE IS THE WORSE HALF.** A native enum needs `ALTER TYPE
... ADD VALUE`, which cannot run inside a transaction in older Postgres and
cannot be removed at all; a VARCHAR with a CHECK is a constraint a migration
rewrites like any other. Nothing in this project is served by the native
type - the values are validated by Pydantic at the edge and by SQLAlchemy in
the session long before Postgres sees them.

`length` is required alongside it for a reason of its own: without one,
`native_enum=False` produces an unbounded VARCHAR, and the CHECK is then the
only thing bounding a column that a migration might later widen.

**TIMESTAMPS ARE STORED NAIVE**, in UTC, which is what
`app/core/time.py`'s `utc_now()` returns and what `_stamp_utc` puts the `Z`
back onto at the edge. 64 of the 80 timestamp columns that predate today
are plain `DateTime`, including every one on the organization surface.

**WHAT THE MINORITY SPELLING COSTS, measured 2026-09-17.**
`app/models/nomination.py` was first written with
`DateTime(timezone=True)`. Postgres hands those back as aware values, so
`nomination.token_expires_at <= utc_now()` raised `can't compare
offset-naive and offset-aware datetimes` - at runtime, inside the
token-expiry check on an unauthenticated endpoint, rather than anywhere a
type or a migration would have caught it. The sixteen aware columns that
already exist are grandfathered by name below rather than silently
tolerated, so the list can only shrink.
"""

import pytest
from sqlalchemy import Enum

import app.models  # noqa: F401 - registers every table on Base.metadata
from app.db.base import Base


def enum_columns():
    """Every enum-typed column in the schema, as (table, column, type)."""
    found = []
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        for column in table.columns:
            if isinstance(column.type, Enum):
                found.append((table.name, column.name, column.type))
    return found


def test_the_schema_has_enum_columns_at_all():
    """Otherwise the checks below pass by finding nothing to check."""
    assert len(enum_columns()) > 20


@pytest.mark.parametrize(
    "table,column",
    [(table, column) for table, column, _ in enum_columns()],
)
def test_the_column_is_not_a_native_postgres_type(table, column):
    """Named per column so a failure says which model to fix."""
    kind = next(k for t, c, k in enum_columns() if (t, c) == (table, column))
    assert kind.native_enum is False, (
        f"{table}.{column} is a native Postgres enum. Declare it "
        f"`Enum({kind.enum_class.__name__ if kind.enum_class else '...'}, "
        "native_enum=False, length=N)` - see this file's header for what the "
        "native type costs at downgrade time."
    )


@pytest.mark.parametrize(
    "table,column",
    [(table, column) for table, column, _ in enum_columns()],
)
def test_the_column_says_how_wide_it_is(table, column):
    kind = next(k for t, c, k in enum_columns() if (t, c) == (table, column))
    assert kind.length, f"{table}.{column} has no length, so it is an unbounded VARCHAR."


@pytest.mark.parametrize(
    "table,column",
    [(table, column) for table, column, _ in enum_columns()],
)
def test_every_value_fits_the_length_it_declares(table, column):
    """A value longer than the column is a write that fails in production only.

    The enum is fine in Python, fine in Pydantic, and fine in every test that
    uses the short values - and the row that finally carries the long one is
    somebody's.
    """
    kind = next(k for t, c, k in enum_columns() if (t, c) == (table, column))
    longest = max(kind.enums, key=len)
    assert len(longest) <= kind.length, (
        f"{table}.{column} declares length={kind.length} and its longest value {longest!r} is {len(longest)} characters."
    )


def timestamp_columns():
    """Every DateTime column in the schema, as (table, column, type)."""
    from sqlalchemy import DateTime

    found = []
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        for column in table.columns:
            if isinstance(column.type, DateTime):
                found.append((table.name, column.name, column.type))
    return found


def test_the_schema_has_timestamps_at_all():
    assert len(timestamp_columns()) > 50


def test_most_timestamps_are_naive_so_the_convention_is_still_the_convention():
    """A summary rather than a per-column rule, because sixteen predate it.

    Written as a ratio on purpose: this is the evidence for the claim in the
    header, and it goes red if somebody starts migrating the other way without
    saying so.
    """
    columns = timestamp_columns()
    naive = [c for c in columns if c[2].timezone is False]
    assert len(naive) / len(columns) > 0.75, (
        f"only {len(naive)} of {len(columns)} timestamp columns are naive - "
        "app/core/time.py's utc_now() returns a naive value, so the two "
        "spellings cannot be compared to each other."
    )


@pytest.mark.parametrize(
    "table,column",
    [
        (table, column)
        for table, column, kind in timestamp_columns()
        if table
        in {
            "org_nominations",
            "nomination_sources",
            "nomination_contacts",
            "nomination_refusals",
            "challenge_spends",
            "email_sends",
            "email_suppressions",
        }
    ],
)
def test_the_nomination_and_mail_timestamps_are_naive(table, column):
    """Named for the tables the defect was actually found in.

    Every one of these is compared against `utc_now()` somewhere -
    `token_expires_at` on an unauthenticated route, `expires_at` on the
    challenge ledger - so an aware spelling here is a 500 rather than a
    mismatch nobody notices.
    """
    kind = next(k for t, c, k in timestamp_columns() if (t, c) == (table, column))
    assert kind.timezone is False, (
        f"{table}.{column} carries an offset while utc_now() does not. "
        "Use a plain `DateTime` - see this file's header for what the mixed "
        "spelling cost."
    )
