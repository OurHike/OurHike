"""`/day-hikes/sync` end to end (#976), against the real FastAPI TestClient.

The trips suite (tests/test_routers_synced_trips.py) mirrored over the
day-hike exchange, because the exchange itself is a mirror: same conflict
rule (`app/core/trip_sync.py`, shared rather than copied), same watermark,
same tombstones, same 404-not-403 posture on ids that are not yours.

The one test with no counterpart in the trips suite is the isolation pair at
the bottom, and it is the reason `synced_day_hikes` is its own table at all:
deployed clients consume `/trips/sync` and validate every returned document
as a trip, so a day hike must never ride that exchange - nor a trip this
one. `app/models/synced_day_hike.py` carries the argument; these tests are
what keep it true.
"""

from __future__ import annotations

import re

from tests.tokens import auth_headers

HIKER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SOMEBODY_ELSE = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _day_hike(day_hike_id="day-hike-1", name="McAfee Knob", **over) -> dict:
    return {
        "id": day_hike_id,
        # Deliberately NOT a trip's shape (no `plan`): the exchange carries
        # the document opaquely, and a suite whose fixtures happened to look
        # like trips would prove less about the isolation tests below.
        "document": {"name": name, "segments": []},
        "base_updated_at": None,
        "deleted": False,
        **over,
    }


def _sync(client, user_id, **body):
    response = client.post("/day-hikes/sync", json=body, headers=auth_headers(user_id))
    assert response.status_code == 200, response.text
    return response.json()


def _trips_sync(client, user_id, **body):
    response = client.post("/trips/sync", json=body, headers=auth_headers(user_id))
    assert response.status_code == 200, response.text
    return response.json()


def _names(payload) -> list[str]:
    return sorted(row["document"]["name"] for row in payload["day_hikes"] if row["document"] is not None)


def test_sync_requires_an_account(client):
    assert client.post("/day-hikes/sync", json={}).status_code == 401


def test_a_first_sync_uploads_and_gets_its_own_stamps_back(client):
    body = _sync(client, HIKER, since=None, day_hikes=[_day_hike()])

    assert _names(body) == ["McAfee Knob"]
    assert body["day_hikes"][0]["updated_at"] is not None
    assert body["now"] is not None
    assert body["conflicts"] == 0


def test_a_second_device_signing_in_receives_the_day_hikes(client):
    _sync(client, HIKER, since=None, day_hikes=[_day_hike()])

    # The point of #976's "sync from day one": the day hike planned on the
    # laptop exists on the phone.
    body = _sync(client, HIKER, since=None, day_hikes=[])

    assert _names(body) == ["McAfee Knob"]


def test_a_watermark_asks_only_for_what_changed(client):
    first = _sync(client, HIKER, since=None, day_hikes=[_day_hike()])

    unchanged = _sync(client, HIKER, since=first["now"], day_hikes=[])

    # Empty because nothing MOVED, not because nothing exists - the day hike
    # is still there for a since=None reader.
    assert unchanged["day_hikes"] == []
    assert _names(_sync(client, HIKER, since=None, day_hikes=[])) == ["McAfee Knob"]


def test_an_edit_carrying_the_stamp_it_saw_is_an_ordinary_edit(client):
    """`base_updated_at` matching the stored stamp means nobody else wrote.

    One row, rewritten in place, no conflict and no copy - the everyday case
    the conflict machinery must leave alone.
    """
    seeded = _sync(client, HIKER, since=None, day_hikes=[_day_hike()])
    stamp = seeded["day_hikes"][0]["updated_at"]

    edited = _sync(
        client,
        HIKER,
        since=None,
        day_hikes=[_day_hike(name="McAfee Knob, before the crowds", base_updated_at=stamp)],
    )

    assert edited["conflicts"] == 0
    assert _names(edited) == ["McAfee Knob, before the crowds"]
    assert len(edited["day_hikes"]) == 1


def test_a_first_sync_is_told_about_deletions_it_never_saw(client):
    """A device that has never synced must hear about tombstones.

    Otherwise it re-uploads the deleted day hike for ever, and the hiker's
    own delete never sticks.
    """
    created = _sync(client, HIKER, since=None, day_hikes=[_day_hike()])
    stamp = created["day_hikes"][0]["updated_at"]
    _sync(
        client,
        HIKER,
        since=created["now"],
        day_hikes=[_day_hike(document=None, base_updated_at=stamp, deleted=True)],
    )

    fresh = _sync(client, HIKER, since=None, day_hikes=[])

    assert [row["id"] for row in fresh["day_hikes"]] == ["day-hike-1"]
    assert fresh["day_hikes"][0]["document"] is None
    assert fresh["day_hikes"][0]["deleted_at"] is not None


def test_two_devices_editing_offline_both_survive_the_reconcile(client):
    """The trips exchange's non-negotiable rule, holding here too.

    Both devices sync, both go offline, both edit the same day hike, both
    come back. Neither edit may be silently rewritten.
    """
    seeded = _sync(client, HIKER, since=None, day_hikes=[_day_hike()])
    stamp = seeded["day_hikes"][0]["updated_at"]
    watermark = seeded["now"]

    # Device A comes back first and wins the id.
    _sync(
        client,
        HIKER,
        since=watermark,
        day_hikes=[_day_hike(name="McAfee Knob via the fire road", base_updated_at=stamp)],
    )

    # Device B was offline the whole time, so it is still working from the
    # stamp it saw before A wrote.
    after_b = _sync(
        client,
        HIKER,
        since=watermark,
        day_hikes=[_day_hike(name="McAfee Knob the short way", base_updated_at=stamp)],
    )

    assert after_b["conflicts"] == 1
    everything = _names(_sync(client, HIKER, since=None, day_hikes=[]))
    assert "McAfee Knob via the fire road" in everything
    assert any("short way" in name for name in everything), "device B's planning was silently discarded"
    assert len(everything) == 2


def test_a_conflict_copy_says_where_it_came_from(client):
    seeded = _sync(client, HIKER, since=None, day_hikes=[_day_hike()])
    stamp = seeded["day_hikes"][0]["updated_at"]
    _sync(client, HIKER, since=None, day_hikes=[_day_hike(name="A's version", base_updated_at=stamp)])

    _sync(client, HIKER, since=None, day_hikes=[_day_hike(name="B's version", base_updated_at=stamp)])

    copies = [n for n in _names(_sync(client, HIKER, since=None, day_hikes=[])) if "another device" in n]

    # Same shared naming rule as trips (`core/trip_sync.py`): no device name
    # to print, so the copy says the true thing instead.
    assert len(copies) == 1
    assert re.fullmatch(r"B's version \(edited on another device, \d{4}-\d{2}-\d{2}\)", copies[0]), copies[0]


def test_one_hikers_day_hike_id_is_not_writable_by_another(client):
    """A client-minted UUID is an id that arrives from outside.

    Silently dropped rather than refused, exactly as `/trips/sync` does it: a
    collision with a stranger's id is not something a hiker can act on, and
    an error naming it would answer a question nobody should be able to ask
    (the 404-not-403 rule).
    """
    _sync(client, HIKER, since=None, day_hikes=[_day_hike(name="Mine")])

    body = _sync(client, SOMEBODY_ELSE, since=None, day_hikes=[_day_hike(name="Theirs")])

    assert body["day_hikes"] == []
    assert _names(_sync(client, HIKER, since=None, day_hikes=[])) == ["Mine"]


def test_one_hikers_day_hikes_are_never_returned_to_another(client):
    _sync(client, HIKER, since=None, day_hikes=[_day_hike()])

    assert _sync(client, SOMEBODY_ELSE, since=None, day_hikes=[])["day_hikes"] == []


def test_an_invented_key_is_refused_rather_than_dropped(client):
    """`extra="forbid"`, the same posture as trips and preferences.

    A key silently dropped is a client believing it synced something it did
    not.
    """
    response = client.post(
        "/day-hikes/sync",
        json={"since": None, "day_hikes": [], "surprise": True},
        headers=auth_headers(HIKER),
    )

    assert response.status_code == 422


# --- The isolation pair: the reason this is a separate table ----------------


def test_a_day_hike_never_appears_in_the_trips_exchange(client):
    """Deployed clients' `tripsSync.ts` validates every `/trips/sync` row as
    a trip and drops (or worse, files) what it gets - so a day-hike document
    reaching that exchange is the failure the separate table exists to make
    impossible. The id is deliberately the same in both stores: the two
    exchanges must not even share an id space.
    """
    _sync(client, HIKER, since=None, day_hikes=[_day_hike(day_hike_id="shared-id", name="A day hike")])

    trips = _trips_sync(client, HIKER, since=None, trips=[])

    assert trips["trips"] == []


def test_a_trip_never_appears_in_the_day_hikes_exchange(client):
    """The other direction of the same wall, same reason."""
    _trips_sync(
        client,
        HIKER,
        since=None,
        trips=[
            {"id": "shared-id", "document": {"name": "A trip", "plan": {"stops": []}}, "base_updated_at": None, "deleted": False}
        ],
    )

    day_hikes = _sync(client, HIKER, since=None, day_hikes=[])

    assert day_hikes["day_hikes"] == []


def test_the_same_id_in_both_exchanges_is_two_documents_that_never_meet(client):
    """One hiker, one client-minted id, one trip and one day hike under it.

    Each exchange returns exactly its own kind, unconflicted: the id spaces
    are independent because the tables are, and neither upload is treated as
    an edit (or a foreign id) of the other.
    """
    _trips_sync(
        client,
        HIKER,
        since=None,
        trips=[
            {
                "id": "shared-id",
                "document": {"name": "The trip", "plan": {"stops": []}},
                "base_updated_at": None,
                "deleted": False,
            }
        ],
    )
    minted = _sync(client, HIKER, since=None, day_hikes=[_day_hike(day_hike_id="shared-id", name="The day hike")])
    assert minted["conflicts"] == 0

    trips = _trips_sync(client, HIKER, since=None, trips=[])
    day_hikes = _sync(client, HIKER, since=None, day_hikes=[])

    assert [row["document"]["name"] for row in trips["trips"]] == ["The trip"]
    assert _names(day_hikes) == ["The day hike"]
