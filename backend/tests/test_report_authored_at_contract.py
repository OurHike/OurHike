"""The 422 the client reads to tell a clock apart from an old app (#412).

`POST /reports` returns 422 for two unrelated reasons:

1. **This app's own rule** - `authored_at` more than five minutes ahead, which
   is a statement about the hiker's phone clock.
2. **Ordinary request validation** - a required field an older client does not
   send, a value it still sends that this API no longer accepts. That is
   version skew, which RELEASING.md §8c's support window bounds and cannot
   prevent past its edge.

They need opposite handling on the client. The clock case is about one report
and resolves when real time catches up to the timestamp it carries; skew is
about the whole app, resolves when it updates, and telling somebody to check
their clock sends them to look at a setting that is fine.

`client/src/lib/api.ts` tells them apart by asking which field the server
named: the `authored_at` rule puts that field in `loc`, and nothing else does.
**That is a cross-boundary assumption, and the client cannot notice on its own
if this side stops holding it** - it would simply start calling every clock
refusal an outdated app, on the screen a hiker reads after finally getting
signal. So it is pinned here, where a change to the schema breaks a backend
test rather than a phone on a ridge.

The same posture as tests/test_preferences_contract.py, which reads a client
file to keep the two halves of `UserPreferences` in step.
"""

import uuid
from datetime import datetime, timedelta, timezone

from tests.tokens import auth_headers

_BASE = {
    "type": "blowdown",
    "reporter_type": "thru",
    "lat": 35.6,
    "lon": -83.5,
    "note": "Large tree across the trail near the gap.",
}


def _locations(body: dict) -> list[list]:
    """Every `loc` FastAPI reported, as plain lists."""
    return [list(entry.get("loc", [])) for entry in body.get("detail", [])]


def test_a_future_authored_at_names_the_field_in_loc(client):
    """The assumption client/src/lib/api.ts rests on."""
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    response = client.post(
        "/reports",
        json=dict(_BASE, authored_at=future),
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 422
    assert any("authored_at" in loc for loc in _locations(response.json()))


def test_ordinary_validation_does_not_name_authored_at(client):
    """The other half, and the one that makes the check discriminating rather
    than merely true.

    A missing required field is what an older client's request looks like to a
    newer API. If this named `authored_at` too, the client's test would pass
    while classifying every skew failure as a clock problem.
    """
    missing_reporter_type = {key: value for key, value in _BASE.items() if key != "reporter_type"}

    response = client.post(
        "/reports",
        json=missing_reporter_type,
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 422
    locations = _locations(response.json())
    assert locations, "expected FastAPI to report which field was wrong"
    assert not any("authored_at" in loc for loc in locations)


def test_an_unknown_field_is_reported_without_naming_authored_at(client):
    """The other shape version skew takes: a field a NEWER client sends that
    this build does not know. Whether it 422s or is ignored depends on the
    schema's extra policy - what matters here is only that it never comes back
    claiming the clock was wrong."""
    response = client.post(
        "/reports",
        json=dict(_BASE, invented_by_a_later_release="whatever"),
        headers=auth_headers(str(uuid.uuid4())),
    )

    if response.status_code == 422:
        assert not any("authored_at" in loc for loc in _locations(response.json()))
    else:
        # Accepted and ignored, which is also fine - the client only ever
        # classifies a 422.
        assert response.status_code in (200, 201)


def test_the_refusal_body_is_json_the_client_can_parse(client):
    """`ApiError` reads the body with `response.json()` and swallows failures,
    so a non-JSON 422 would silently become "outdated app" for every clock
    refusal."""
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    response = client.post(
        "/reports",
        json=dict(_BASE, authored_at=future),
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.headers["content-type"].startswith("application/json")
    assert isinstance(response.json().get("detail"), list)
