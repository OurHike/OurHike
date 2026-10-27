"""The golden batch, posted to the server (#1902).

`client/src/lib/usageBatch.golden.json` is one row of every usage event,
carrying every optional field, built by the phone's own code -
client/src/lib/usageBatch.golden.test.ts fails when what the phone builds
stops matching it. This half posts the same file to `POST /usage-events` and
requires every row stored, field for field.

The two halves exist because the drift between them is silent everywhere
else: a field renamed on one side makes the server refuse the row, the phone
drops refused rows without a trace, and the only symptom is a count that
comes in low. `analytics_intake` would show it after release; this shows it
before merge.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from app.core.analytics_rollup import month_start
from app.core.analytics_seal import month_label, month_public_key, new_secret
from app.models.analytics import AnalyticsEvent, AnalyticsSealKey
from app.schemas.analytics import UsageEventIn

GOLDEN = Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "usageBatch.golden.json"

# Read by tests/test_ci_scope.py, which fails if backend-tests.yml's scope list
# stops naming this file - a client-only pull request is the one that changes it.
CLIENT_FILES_READ = (GOLDEN,)


def _golden() -> dict:
    assert GOLDEN.exists(), f"{GOLDEN} is missing, so nothing can be compared"
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture()
def golden_day(monkeypatch):
    """Today, for the server, is the day after the golden rows were dated -
    the one field the file cannot keep current is the date."""
    day = date.fromisoformat(_golden()["events"][0]["local_date"])
    monkeypatch.setattr("app.routers.analytics.utc_now", lambda: datetime.combine(day + timedelta(days=1), time(12)))
    return day


def test_every_golden_row_passes_the_registry_on_its_own():
    for event in _golden()["events"]:
        UsageEventIn.model_validate(event)


def test_the_golden_batch_names_every_event_the_server_accepts():
    from app.models.analytics import UsageEvent

    assert {event["event"] for event in _golden()["events"]} == {event.value for event in UsageEvent}


def test_the_server_stores_every_golden_row_as_the_phone_sent_it(client, db_session, golden_day):
    secret = new_secret()
    month = month_start(golden_day)
    db_session.add(AnalyticsSealKey(month=month, public_key=month_public_key(secret, month_label(month))))
    db_session.commit()
    batch = _golden()

    response = client.post("/usage-events", json=batch)

    assert response.status_code == 202
    assert response.json() == {"accepted": len(batch["events"]), "duplicates": 0, "refused": 0}
    for sent in batch["events"]:
        stored = db_session.get(AnalyticsEvent, sent["id"])
        assert stored is not None, sent["id"]
        for field in (
            "week_first",
            "month_first",
            "ever_first",
            "kind_month_first",
            "month_returning",
            "signed_in",
            "app_version",
            "miles",
            "pageviews",
        ):
            assert getattr(stored, field) == sent.get(field), (sent["event"], field)
        assert stored.event.value == sent["event"] and stored.platform.value == sent["platform"]
        assert stored.local_date.isoformat() == sent["local_date"]
        assert (stored.club_firsts or []) == sent["club_firsts"]
        assert stored.clubs == sent.get("clubs")
        assert stored.has_fix is ("fix" in sent)
        assert (stored.session_length.value if stored.session_length else None) == sent.get("session_length")
