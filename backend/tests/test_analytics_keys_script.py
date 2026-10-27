"""`scripts/analytics_keys.py`: publishing the public keys, and opening rows (#1902).

The opening's record is written and committed BEFORE anything is opened, and
publishing refuses to replace a month's key with a different secret's - the
two ways this script could quietly lose track of what was sealed and who read it.
"""

import importlib.util
import uuid
from datetime import date
from pathlib import Path

import pytest

from app.core.analytics_seal import month_label, month_public_key, new_secret, seal
from app.models.analytics import AnalyticsEvent, AnalyticsOpening, AnalyticsSealKey

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analytics_keys.py"
OCTOBER = date(2026, 10, 1)


@pytest.fixture(scope="module")
def keys():
    spec = importlib.util.spec_from_file_location("analytics_keys", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sealed_event(db_session, secret: bytes, payload: dict, *, user_key: str | None = None) -> AnalyticsEvent:
    event_id = str(uuid.uuid4())
    event = AnalyticsEvent(
        id=event_id,
        local_date=date(2026, 10, 3),
        received_on=date(2026, 10, 3),
        event="map_screen_viewed",
        platform="ios",
        user_key=user_key,
        has_fix=True,
        seal="sealed",
        sealed=seal(month_public_key(secret, "2026-10"), "2026-10", event_id, payload),
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_a_secret_survives_being_written_down_and_read_back(keys):
    secret = new_secret()

    assert keys.decode_secret(keys.encode_secret(secret)) == secret


def test_something_that_is_not_a_secret_is_refused(keys):
    with pytest.raises(keys.KeysError):
        keys.decode_secret("hunter2")


def test_publishing_writes_each_months_public_key(db_session, keys):
    secret = new_secret()

    written = keys.publish(db_session, secret, OCTOBER, 3)

    assert written == [date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1)]
    stored = db_session.get(AnalyticsSealKey, date(2026, 11, 1))
    assert bytes(stored.public_key) == month_public_key(secret, month_label(date(2026, 11, 1)))


def test_publishing_again_with_the_same_secret_is_a_no_op(db_session, keys):
    secret = new_secret()
    keys.publish(db_session, secret, OCTOBER, 2)

    assert keys.publish(db_session, secret, OCTOBER, 2) == []


def test_publishing_a_different_secret_over_a_month_is_refused(db_session, keys):
    keys.publish(db_session, new_secret(), OCTOBER, 1)

    with pytest.raises(keys.KeysError):
        keys.publish(db_session, new_secret(), OCTOBER, 1)


def test_opening_records_who_and_why_and_writes_the_rows_to_a_file(db_session, keys, tmp_path):
    secret = new_secret()
    event = _sealed_event(db_session, secret, {"account": "acct-1", "lat": 41.29871, "lon": -74.1881})
    out = tmp_path / "opened.csv"

    opened = keys.open_rows(
        db_session,
        secret,
        month=OCTOBER,
        opened_by="Test Maintainer",
        reason="checking the sealing works",
        event_id=event.id,
        key=None,
        out=out,
    )

    assert opened == 1
    assert "41.29871" in out.read_text() and "acct-1" in out.read_text()
    record = db_session.query(AnalyticsOpening).one()
    assert (record.opened_by, record.selector, record.rows_opened) == (
        "Test Maintainer",
        f"event {event.id}",
        1,
    )


def test_the_record_is_committed_even_when_opening_fails(db_session, keys, tmp_path):
    """A crash halfway must not leave an opening off the record."""
    secret = new_secret()
    _sealed_event(db_session, secret, {"lat": 41.3, "lon": -74.2})
    unwritable = tmp_path / "no-such-directory" / "opened.csv"

    with pytest.raises(OSError):
        keys.open_rows(
            db_session,
            secret,
            month=OCTOBER,
            opened_by="Test Maintainer",
            reason="a run that crashes",
            event_id=None,
            key=None,
            out=unwritable,
        )

    db_session.rollback()
    assert db_session.query(AnalyticsOpening).count() == 1


def test_an_opening_needs_a_reason(db_session, keys, tmp_path):
    with pytest.raises(keys.KeysError):
        keys.open_rows(
            db_session,
            new_secret(),
            month=OCTOBER,
            opened_by="Test Maintainer",
            reason="  ",
            event_id=None,
            key=None,
            out=tmp_path / "x.csv",
        )


def test_the_wrong_secret_opens_nothing(db_session, keys, tmp_path):
    _sealed_event(db_session, new_secret(), {"lat": 41.3, "lon": -74.2})
    out = tmp_path / "opened.csv"

    opened = keys.open_rows(
        db_session,
        new_secret(),
        month=OCTOBER,
        opened_by="Test Maintainer",
        reason="the wrong secret",
        event_id=None,
        key=None,
        out=out,
    )

    assert opened == 0
    assert "41.3" not in out.read_text()
