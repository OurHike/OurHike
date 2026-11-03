"""The usage-event registry, compared across the two languages it is written in (#1902).

`client/src/lib/usageEvents.ts` and `app/models/analytics.py` hold the same
lists - the six events, the session-length buckets, the platforms, the
reserved "club not recorded" id - and `POST /usage-events` refuses anything
the backend's half does not name. So a name added on the phone alone does not
fail loudly: each row carrying it is refused, alone, inside a 202 that
accepts the rest of its batch; the phone drops the refused row, and the only
trace is a count of `invalid` rows in `analytics_intake`. The event is simply
never counted. This test is the only place that drift would be noticed before
a month of numbers went missing.

Read as text for the reason tests/test_preferences_contract.py gives: a list
restated here would be a third copy to keep in step.
"""

import re
from pathlib import Path

from app.models.analytics import SessionLength, UsageEvent, UsagePlatform
from app.schemas.analytics import CLUB_NOT_RECORDED

CLIENT_REGISTRY = Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "usageEvents.ts"

# Read by tests/test_ci_scope.py, which fails if backend-tests.yml's scope list
# stops naming this file - a client-only pull request is the one that drifts.
CLIENT_FILES_READ = (CLIENT_REGISTRY,)


def _client_source() -> str:
    assert CLIENT_REGISTRY.exists(), f"{CLIENT_REGISTRY} is missing, so nothing can be compared"
    return CLIENT_REGISTRY.read_text(encoding="utf-8")


def _quoted(text: str) -> list[str]:
    return re.findall(r"'([a-z0-9_]+)'", text)


def test_the_phone_sends_exactly_the_events_the_server_accepts():
    block = re.search(r"export const USAGE_EVENTS = \[(.*?)\] as const", _client_source(), re.DOTALL)
    assert block is not None, "USAGE_EVENTS is not where this test reads it"

    assert _quoted(block.group(1)) == [event.value for event in UsageEvent]


def test_the_session_buckets_match():
    line = re.search(r"export type SessionLength = (.*)", _client_source())
    assert line is not None

    assert sorted(_quoted(line.group(1))) == sorted(bucket.value for bucket in SessionLength)


def test_the_platforms_match():
    line = re.search(r"export type UsagePlatform = (.*)", _client_source())
    assert line is not None

    assert sorted(_quoted(line.group(1))) == sorted(platform.value for platform in UsagePlatform)


def test_the_reserved_club_id_matches():
    line = re.search(r"export const CLUB_NOT_RECORDED = '([^']+)'", _client_source())
    assert line is not None

    assert line.group(1) == CLUB_NOT_RECORDED
