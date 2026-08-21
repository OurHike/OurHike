"""The conflict rule (#892), which the issue calls non-negotiable.

Every test here is a way the rule could lose somebody's planning, so they
are written as the loss rather than as the mechanism: "both survive" rather
than "returns two writes".

The one that matters most is `test_two_devices_editing_the_same_trip_both_survive`.
If it ever goes green by returning ONE write, this app has become the thing
features/ACCOUNT_SYNC.md exists to stop it being.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.trip_sync import (
    StoredTrip,
    UploadedTrip,
    name_for_copy,
    resolve_upload,
)

NOW = datetime(2026, 8, 21, 12, 0, 0)
EARLIER = NOW - timedelta(hours=3)
LATER = NOW + timedelta(hours=1)


def _doc(name="Grayson Highlands", **over) -> dict:
    return {"name": name, "plan": {"stops": []}, **over}


#: "you did not say", which is NOT the same as passing None - None is the
#: document a tombstone carries, and a helper that conflated the two would
#: have silently turned every delete test into an edit test.
UNSAID = object()


def _stored(document=UNSAID, updated_at=EARLIER, deleted_at=None) -> StoredTrip:
    return StoredTrip(
        id="trip-1",
        document=_doc() if document is UNSAID else document,
        updated_at=updated_at,
        deleted_at=deleted_at,
    )


def _upload(document=UNSAID, base_updated_at=EARLIER, deleted=False) -> UploadedTrip:
    return UploadedTrip(
        id="trip-1",
        document=_doc() if document is UNSAID else document,
        base_updated_at=base_updated_at,
        deleted=deleted,
    )


def _ids():
    return iter(["copy-1", "copy-2"])


def _counter():
    ids = _ids()
    return lambda: next(ids)


class TestTheOrdinaryCases:
    def test_a_trip_the_server_has_never_seen_is_written(self):
        writes = resolve_upload(_upload(base_updated_at=None), None, NOW, _counter())

        assert [(w.id, w.deleted) for w in writes] == [("trip-1", False)]

    def test_an_edit_on_top_of_what_this_device_last_saw_is_an_ordinary_update(self):
        writes = resolve_upload(_upload(_doc("Renamed")), _stored(), NOW, _counter())

        assert len(writes) == 1
        assert writes[0].id == "trip-1"
        assert writes[0].document["name"] == "Renamed"
        assert not writes[0].is_conflict_copy

    def test_the_hikers_own_delete_travels(self):
        writes = resolve_upload(_upload(None, deleted=True), _stored(), NOW, _counter())

        assert [(w.id, w.deleted, w.document) for w in writes] == [("trip-1", True, None)]

    def test_a_delete_of_a_trip_the_server_never_saw_still_writes_the_tombstone(self):
        # Not a no-op: the tombstone is what stops ANOTHER device that does
        # have the trip from re-uploading it for ever.
        writes = resolve_upload(_upload(None, base_updated_at=None, deleted=True), None, NOW, _counter())

        assert [(w.id, w.deleted) for w in writes] == [("trip-1", True)]


class TestTheRuleThatIsNotNegotiable:
    def test_two_devices_editing_the_same_trip_both_survive(self):
        """The load-bearing test in this file.

        Device A edited and synced; device B was offline holding its own
        edit against the older stamp. B's upload must not overwrite A's.
        """
        stored = _stored(_doc("Grayson Highlands, four days"), updated_at=LATER)
        uploaded = _upload(_doc("Grayson Highlands, three days"), base_updated_at=EARLIER)

        writes = resolve_upload(uploaded, stored, NOW, _counter())

        # The stored row is not written at all - untouched is how it survives.
        assert [w.id for w in writes] == ["copy-1"]
        assert writes[0].is_conflict_copy
        assert "three days" in writes[0].document["name"]

    def test_the_copy_says_what_is_actually_known_about_where_it_came_from(self):
        # The doc's example names a device. The client has none to give, so
        # the copy says the true thing instead: another device, this date.
        assert name_for_copy(_doc(), NOW) == ("Grayson Highlands (edited on another device, 2026-08-21)")

    def test_an_unnamed_trip_still_gets_a_name_rather_than_a_bare_suffix(self):
        assert name_for_copy(None, NOW).startswith("Untitled trip (")

    def test_a_device_that_thinks_a_trip_is_new_over_one_that_exists_keeps_both(self):
        # Two devices minted the same id, or one is re-uploading a trip it
        # created before a sync it has forgotten. Either way, not an
        # overwrite.
        writes = resolve_upload(_upload(_doc("Mine"), base_updated_at=None), _stored(), NOW, _counter())

        assert [w.id for w in writes] == ["copy-1"]

    def test_a_delete_against_another_devices_edit_keeps_the_edit(self):
        """The case the doc does not specify.

        The tombstone lands, and the OTHER device's work is kept beside it.
        Both acts were the hiker's; this resolves toward the rule that is
        non-negotiable rather than the one that is convenient.
        """
        stored = _stored(_doc("Grayson Highlands, four days"), updated_at=LATER)

        writes = resolve_upload(_upload(None, base_updated_at=EARLIER, deleted=True), stored, NOW, _counter())

        assert [(w.id, w.deleted) for w in writes] == [("trip-1", True), ("copy-1", False)]
        assert "four days" in writes[1].document["name"]


class TestWhatIsNotAConflict:
    def test_the_same_delete_arriving_twice_does_not_resurrect_anything(self):
        # Deleted on both devices while neither had heard from the other.
        # Writing a copy here would hand back a trip the hiker deleted twice.
        stored = _stored(None, updated_at=LATER, deleted_at=LATER)

        writes = resolve_upload(_upload(None, base_updated_at=EARLIER, deleted=True), stored, NOW, _counter())

        assert writes == []

    def test_re_uploading_an_identical_trip_writes_nothing(self):
        # A device syncing twice, not two people disagreeing. Compared by
        # content, because the stamp is exactly what is out of date here.
        stored = _stored(_doc(), updated_at=LATER)

        writes = resolve_upload(_upload(_doc(), base_updated_at=EARLIER), stored, NOW, _counter())

        assert writes == []

    def test_an_identical_re_upload_is_not_confused_with_an_edit_back(self):
        # Two devices genuinely disagreeing about the name, where one of them
        # happens to match neither the stored doc nor the other upload.
        stored = _stored(_doc("Server's name"), updated_at=LATER)

        writes = resolve_upload(_upload(_doc("Device's name"), base_updated_at=EARLIER), stored, NOW, _counter())

        assert len(writes) == 1
        assert writes[0].is_conflict_copy


class TestNothingIsEverDestroyed:
    def test_no_resolution_anywhere_writes_over_a_row_this_device_had_not_seen(self):
        """The invariant behind every case above, asserted once directly.

        Whenever the stored stamp is not the one the device is working from,
        no write may carry the stored row's id with a document on it - that
        is precisely what overwriting somebody else's edit looks like.
        """
        stale = _stored(_doc("Somebody else's work"), updated_at=LATER)

        for uploaded in (
            _upload(_doc("Mine"), base_updated_at=EARLIER),
            _upload(_doc("Mine"), base_updated_at=None),
            _upload(None, base_updated_at=EARLIER, deleted=True),
        ):
            writes = resolve_upload(uploaded, stale, NOW, _counter())
            overwrites = [w for w in writes if w.id == stale.id and w.document is not None]

            assert overwrites == [], f"{uploaded} overwrote a row it had not seen"
