"""`/trips/sync` end to end (#892), against the real FastAPI TestClient.

features/ACCOUNT_SYNC.md phase B. The conflict rule itself is tested in
tests/test_core_trip_sync.py with no database at all; what is tested here is
everything the rule cannot see - the delta, the watermark, the tombstones
travelling, and that one hiker's trips are not reachable by another.

The issue asks for one test specifically: "edit on A offline, edit on B
offline, reconcile, assert BOTH survive and neither is silently rewritten."
That is `test_two_devices_editing_offline_both_survive_the_reconcile`, and it
drives two clients through the real endpoint rather than calling the rule.
"""

from __future__ import annotations

import re

from tests.tokens import auth_headers

HIKER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SOMEBODY_ELSE = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _trip(trip_id="trip-1", name="Grayson Highlands", **over) -> dict:
    return {
        "id": trip_id,
        "document": {"name": name, "plan": {"stops": []}},
        "base_updated_at": None,
        "deleted": False,
        **over,
    }


def _sync(client, user_id, **body):
    response = client.post("/trips/sync", json=body, headers=auth_headers(user_id))
    assert response.status_code == 200, response.text
    return response.json()


def _names(payload) -> list[str]:
    return sorted(row["document"]["name"] for row in payload["trips"] if row["document"] is not None)


def test_sync_requires_an_account(client):
    assert client.post("/trips/sync", json={}).status_code == 401


def test_a_first_sync_uploads_and_gets_its_own_stamps_back(client):
    body = _sync(client, HIKER, since=None, trips=[_trip()])

    assert _names(body) == ["Grayson Highlands"]
    assert body["trips"][0]["updated_at"] is not None
    assert body["now"] is not None
    assert body["conflicts"] == 0


def test_a_second_device_signing_in_receives_the_trips(client):
    _sync(client, HIKER, since=None, trips=[_trip()])

    # The whole point of the feature: the laptop's plan exists on the phone.
    body = _sync(client, HIKER, since=None, trips=[])

    assert _names(body) == ["Grayson Highlands"]


def test_a_watermark_asks_only_for_what_changed(client):
    first = _sync(client, HIKER, since=None, trips=[_trip()])

    unchanged = _sync(client, HIKER, since=first["now"], trips=[])

    # Not an empty response because nothing exists - an empty response
    # because nothing MOVED. The trip is still there for a since=None reader.
    assert unchanged["trips"] == []
    assert _names(_sync(client, HIKER, since=None, trips=[])) == ["Grayson Highlands"]


def test_a_first_sync_is_told_about_deletions_it_never_saw(client):
    """A device that has never synced must hear about tombstones.

    Otherwise it re-uploads the deleted trip for ever, and the hiker's own
    delete never sticks.
    """
    created = _sync(client, HIKER, since=None, trips=[_trip()])
    stamp = created["trips"][0]["updated_at"]
    _sync(
        client,
        HIKER,
        since=created["now"],
        trips=[_trip(document=None, base_updated_at=stamp, deleted=True)],
    )

    fresh = _sync(client, HIKER, since=None, trips=[])

    assert [row["id"] for row in fresh["trips"]] == ["trip-1"]
    assert fresh["trips"][0]["document"] is None
    assert fresh["trips"][0]["deleted_at"] is not None


def test_two_devices_editing_offline_both_survive_the_reconcile(client):
    """The issue's own acceptance test.

    Both devices sync, both go offline, both edit the same trip, both come
    back. Neither edit may be silently rewritten.
    """
    seeded = _sync(client, HIKER, since=None, trips=[_trip()])
    stamp = seeded["trips"][0]["updated_at"]
    watermark = seeded["now"]

    # Device A comes back first and wins the id.
    _sync(
        client,
        HIKER,
        since=watermark,
        trips=[_trip(name="Grayson Highlands, four days", base_updated_at=stamp)],
    )

    # Device B was offline the whole time, so it is still working from the
    # stamp it saw before A wrote.
    after_b = _sync(
        client,
        HIKER,
        since=watermark,
        trips=[_trip(name="Grayson Highlands, three days", base_updated_at=stamp)],
    )

    assert after_b["conflicts"] == 1
    everything = _names(_sync(client, HIKER, since=None, trips=[]))
    assert "Grayson Highlands, four days" in everything
    assert any("three days" in name for name in everything), "device B's four days of planning were silently discarded"
    assert len(everything) == 2


def test_a_conflict_copy_says_where_it_came_from(client):
    seeded = _sync(client, HIKER, since=None, trips=[_trip()])
    stamp = seeded["trips"][0]["updated_at"]
    _sync(client, HIKER, since=None, trips=[_trip(name="A's version", base_updated_at=stamp)])

    _sync(client, HIKER, since=None, trips=[_trip(name="B's version", base_updated_at=stamp)])

    copies = [n for n in _names(_sync(client, HIKER, since=None, trips=[])) if "another device" in n]

    # The doc's example names a device ("from the phone"). The client has no
    # device name to give, so the copy says the true thing instead.
    assert len(copies) == 1
    assert re.fullmatch(r"B's version \(edited on another device, \d{4}-\d{2}-\d{2}\)", copies[0]), copies[0]


def test_one_hikers_trip_id_is_not_writable_by_another(client):
    """A client-minted UUID is an id that arrives from outside.

    Silently dropped rather than refused: a collision with a stranger's id is
    not something a hiker can act on, and an error naming it would answer a
    question nobody should be able to ask.
    """
    _sync(client, HIKER, since=None, trips=[_trip(name="Mine")])

    body = _sync(client, SOMEBODY_ELSE, since=None, trips=[_trip(name="Theirs")])

    assert body["trips"] == []
    assert _names(_sync(client, HIKER, since=None, trips=[])) == ["Mine"]


def test_one_hikers_trips_are_never_returned_to_another(client):
    _sync(client, HIKER, since=None, trips=[_trip()])

    assert _sync(client, SOMEBODY_ELSE, since=None, trips=[])["trips"] == []


def test_the_planned_hike_travels_to_the_second_device(client):
    _sync(
        client,
        HIKER,
        since=None,
        trips=[],
        hike={"start_mile": 1300.0, "end_mile": 1400.0, "base_updated_at": None},
    )

    body = _sync(client, HIKER, since=None, trips=[])

    assert body["hike"]["start_mile"] == 1300.0
    assert body["hike"]["end_mile"] == 1400.0


def test_clearing_the_planned_hike_is_a_decision_with_a_date_rather_than_an_absence(client):
    created = _sync(
        client,
        HIKER,
        since=None,
        trips=[],
        hike={"start_mile": 1300.0, "end_mile": 1400.0, "base_updated_at": None},
    )
    stamp = created["hike"]["updated_at"]

    body = _sync(
        client,
        HIKER,
        since=None,
        trips=[],
        hike={"start_mile": None, "end_mile": None, "base_updated_at": stamp},
    )

    # The row survives with both miles null, which is "the hiker cleared it".
    # A missing row would mean "never synced one" - a different claim.
    assert body["hike"] is not None
    assert body["hike"]["start_mile"] is None


def test_a_device_that_says_nothing_about_the_hike_does_not_clear_it(client):
    """Omitting `hike` and sending a hike with null miles are different.

    Getting this wrong would let any device that has never had a planned hike
    wipe the one the hiker set on another.
    """
    _sync(
        client,
        HIKER,
        since=None,
        trips=[],
        hike={"start_mile": 1300.0, "end_mile": 1400.0, "base_updated_at": None},
    )

    body = _sync(client, HIKER, since=None, trips=[])

    assert body["hike"]["start_mile"] == 1300.0


def test_the_planned_hike_does_not_keep_both_and_the_stale_device_loses(client):
    """The one thing here that is last-write-wins, deliberately.

    Two trips a hiker planned are two plans. Two answers to "where am I
    walking, right now" are not - presenting both would be the app asking a
    question it invented.
    """
    created = _sync(
        client,
        HIKER,
        since=None,
        trips=[],
        hike={"start_mile": 1300.0, "end_mile": 1400.0, "base_updated_at": None},
    )
    stale_stamp = created["hike"]["updated_at"]
    _sync(
        client,
        HIKER,
        since=None,
        trips=[],
        hike={"start_mile": 500.0, "end_mile": 600.0, "base_updated_at": stale_stamp},
    )

    body = _sync(
        client,
        HIKER,
        since=None,
        trips=[],
        hike={"start_mile": 900.0, "end_mile": 1000.0, "base_updated_at": stale_stamp},
    )

    assert body["hike"]["start_mile"] == 500.0


def test_an_invented_key_is_refused_rather_than_dropped(client):
    """`extra="forbid"`, the same posture as preferences (#242's lesson).

    A key silently dropped is a client believing it synced something it did
    not.
    """
    response = client.post(
        "/trips/sync",
        json={"since": None, "trips": [], "surprise": True},
        headers=auth_headers(HIKER),
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Long hikes and the pointer at the one the app is in (#1317).


def _hike(hike_id="hike-1", name="Springer → Katahdin", **over) -> dict:
    return {
        "id": hike_id,
        "document": {
            "id": hike_id,
            "name": name,
            "type": "thru",
            "trailId": "AT",
            "points": [{"mile": 0}, {"mile": 2197.4}],
            "status": "walking",
            "tripIds": [],
        },
        "base_updated_at": None,
        "deleted": False,
        **over,
    }


def _hike_names(payload) -> list[str]:
    return sorted(row["document"]["name"] for row in payload["hikes"] if row["document"] is not None)


def test_a_long_hike_reaches_the_second_device(client):
    _sync(client, HIKER, since=None, hikes=[_hike()])

    body = _sync(client, HIKER, since=None)
    assert _hike_names(body) == ["Springer → Katahdin"]
    assert body["hikes"][0]["document"]["points"] == [{"mile": 0}, {"mile": 2197.4}]


def test_the_pointer_travels_with_the_hike_it_names(client):
    """The whole reason both sync rather than the pointer alone: an id
    arriving on a device that has never heard of the hike names nothing."""
    _sync(
        client,
        HIKER,
        since=None,
        hikes=[_hike()],
        active_hike={"hike_id": "hike-1", "base_updated_at": None},
    )

    body = _sync(client, HIKER, since=None)
    assert body["active_hike"]["hike_id"] == "hike-1"
    assert [row["id"] for row in body["hikes"]] == ["hike-1"]


def test_leaving_the_long_hike_state_is_a_decision_rather_than_an_absence(client):
    """A null pointer is the hiker tapping Day hike, which travels. A device
    that says nothing about it is a different claim - see the next test."""
    first = _sync(
        client,
        HIKER,
        since=None,
        hikes=[_hike()],
        active_hike={"hike_id": "hike-1", "base_updated_at": None},
    )

    _sync(
        client,
        HIKER,
        since=None,
        active_hike={"hike_id": None, "base_updated_at": first["active_hike"]["updated_at"]},
    )

    body = _sync(client, HIKER, since=None)
    assert body["active_hike"]["hike_id"] is None
    # The hike itself is untouched: not leading is not the same as forgotten.
    assert [row["id"] for row in body["hikes"]] == ["hike-1"]


def test_a_device_that_says_nothing_about_the_pointer_does_not_clear_it(client):
    _sync(
        client,
        HIKER,
        since=None,
        hikes=[_hike()],
        active_hike={"hike_id": "hike-1", "base_updated_at": None},
    )

    body = _sync(client, HIKER, since=None, trips=[_trip()])
    assert body["active_hike"]["hike_id"] == "hike-1"


def test_a_forgotten_hike_travels_as_a_tombstone(client):
    """`removeHike`'s act, reaching the other device. The sections are trips
    and are not touched by any of this."""
    first = _sync(client, HIKER, since=None, hikes=[_hike()], trips=[_trip()])
    stamp = first["hikes"][0]["updated_at"]

    _sync(
        client,
        HIKER,
        since=None,
        hikes=[{"id": "hike-1", "document": None, "base_updated_at": stamp, "deleted": True}],
    )

    body = _sync(client, HIKER, since=None)
    assert body["hikes"][0]["deleted_at"] is not None
    assert body["hikes"][0]["document"] is None
    # The walking survives the way of looking at it.
    assert _names(body) == ["Grayson Highlands"]


def test_a_long_hike_does_not_keep_both_and_the_stale_device_loses(client):
    """The decision, end to end.

    Two trips edited offline both survive above
    (`test_two_devices_editing_offline_both_survive_the_reconcile`). Two
    edits to one HIKE do not, because a copy would put the same sections in
    two hikes at once. app/models/synced_hike.py argues it; this asserts it,
    including the cost - device B's name is gone.
    """
    first = _sync(client, HIKER, since=None, hikes=[_hike()])
    stamp = first["hikes"][0]["updated_at"]

    _sync(client, HIKER, since=None, hikes=[_hike(name="From the laptop", base_updated_at=stamp)])
    _sync(client, HIKER, since=None, hikes=[_hike(name="From the phone", base_updated_at=stamp)])

    body = _sync(client, HIKER, since=None)
    assert _hike_names(body) == ["From the laptop"]
    assert len(body["hikes"]) == 1


def test_one_hikers_long_hike_id_is_not_writable_by_another(client):
    _sync(client, HIKER, since=None, hikes=[_hike()])
    _sync(client, SOMEBODY_ELSE, since=None, hikes=[_hike(name="Not yours")])

    mine = _sync(client, HIKER, since=None)
    assert _hike_names(mine) == ["Springer → Katahdin"]


def test_one_hikers_long_hikes_are_never_returned_to_another(client):
    _sync(client, HIKER, since=None, hikes=[_hike()])

    theirs = _sync(client, SOMEBODY_ELSE, since=None)
    assert theirs["hikes"] == []
    assert theirs["active_hike"] is None


def test_a_client_that_says_nothing_about_hikes_still_syncs_its_trips(client):
    """RELEASING.md §8c's expand step, asserted: every shipped build posts a
    body with no `hikes` and no `active_hike` at all."""
    body = _sync(client, HIKER, since=None, trips=[_trip()])

    assert _names(body) == ["Grayson Highlands"]
    assert body["hikes"] == []
    assert body["active_hike"] is None


def test_a_watermark_asks_only_for_the_hikes_that_changed(client):
    first = _sync(client, HIKER, since=None, hikes=[_hike()])

    quiet = _sync(client, HIKER, since=first["now"])
    assert quiet["hikes"] == []

    _sync(client, HIKER, since=None, hikes=[_hike("hike-2", name="Long Trail")])
    body = _sync(client, HIKER, since=first["now"])
    assert _hike_names(body) == ["Long Trail"]
