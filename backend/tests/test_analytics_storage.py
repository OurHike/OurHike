"""What usage measurement holds, and the room it takes on disk (#1902, app/core/analytics_storage.py).

The nightly checks and the report's storage strip read these figures to warn
before the intake gate turns batches away, and before the database reaches
its plan's quota - Supabase's Free plan turns the whole database read-only
past it, the rest of the app included.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.dialects.postgresql import insert

from app.core import analytics_storage
from app.db.base import Base
from app.models.analytics import AnalyticsEvent


def _events(db_session, n: int) -> None:
    db_session.execute(
        insert(AnalyticsEvent.__table__).values(
            [
                {
                    "id": str(uuid.uuid4()),
                    "local_date": date(2026, 11, 1),
                    "received_on": date(2026, 11, 1),
                    "event": "session",
                    "platform": "ios",
                    "week_first": False,
                    "month_first": False,
                    "ever_first": False,
                    "kind_month_first": False,
                    "month_returning": False,
                    "signed_in": False,
                    "has_fix": False,
                    "seal": "none",
                    "pageviews": 3,
                    "session_length": "m1_to_5",
                }
                for _ in range(n)
            ]
        )
    )
    db_session.commit()


def test_usage_tables_names_every_table_usage_measurement_keeps():
    """A usage table left off the list would take room on disk that no warning counts."""
    kept = {name for name in Base.metadata.tables if name.startswith("analytics_")}

    assert set(analytics_storage.USAGE_TABLES) == kept


def test_the_usage_tables_size_on_disk_grows_with_the_rows_in_them(db_session):
    before = analytics_storage.usage_tables_bytes(db_session)
    _events(db_session, 3000)

    after = analytics_storage.usage_tables_bytes(db_session)

    assert after > before > 0


@pytest.mark.real_database_size
def test_the_database_size_counts_at_least_the_usage_tables_in_it(db_session):
    _events(db_session, 100)

    assert analytics_storage.database_bytes(db_session) >= analytics_storage.usage_tables_bytes(db_session) > 0


def test_storage_near_the_ceiling_is_the_nearer_of_rows_held_and_the_tables_size_on_disk(monkeypatch):
    """Rows held are what the intake gate counts; the size on disk is what the
    plan counts, and it runs higher when real rows are larger than the
    measured 382 bytes or the file still holds the room of deleted ones."""
    monkeypatch.setattr(analytics_storage.settings, "analytics_storage_ceiling_mb", 100)
    ceiling_rows = analytics_storage.ceiling_rows()

    rows_nearer = analytics_storage.Storage(rows_held=ceiling_rows // 2, usage_bytes=10 * 1024 * 1024, database_bytes=0)
    disk_nearer = analytics_storage.Storage(rows_held=ceiling_rows // 10, usage_bytes=90 * 1024 * 1024, database_bytes=0)

    assert round(rows_nearer.ceiling_share, 3) == 0.5
    assert round(disk_nearer.ceiling_share, 3) == 0.9


def test_a_limit_of_zero_has_no_share_rather_than_dividing_by_it(monkeypatch):
    """A ceiling of 0 turns every batch away, which `rows_over_budget` already
    says; a quota of 0 is no quota configured."""
    monkeypatch.setattr(analytics_storage.settings, "analytics_storage_ceiling_mb", 0)
    monkeypatch.setattr(analytics_storage.settings, "database_quota_mb", 0)

    storage = analytics_storage.Storage(rows_held=5, usage_bytes=5, database_bytes=5)

    assert storage.ceiling_share is None
    assert storage.quota_share is None
