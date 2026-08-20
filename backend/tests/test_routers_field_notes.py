"""Tests for the `/field-notes` router - dated observations about a place.

See ../../features/FIELD_NOTES.md. The load-bearing behaviours: a note is
visible the moment it lands (§5's publish-now decision, the reverse of
reports'), `observed_at` is the hiker's claim with the same future-bound
`authored_at` carries, `reporter_id` and `posted_at` are withheld from
anonymous readers (§6 - many dated notes from one identifier reconstruct a
hike), and moderation is flag-and-hide where the row is hidden, never
deleted.
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.models.field_note import FieldNote, NoteFlag
from app.models.profile import Role
from tests.factories import make_profile
from tests.tokens import auth_headers

_VALID_PAYLOAD = {
    "poi_id": "atc_shelters:abc-123",
    "lat": 35.6,
    "lon": -83.5,
    "mile": 207.3,
    "observation": "dry",
    "reporter_type": "section",
}


def _post_note(client, user_id, **overrides):
    return client.post(
        "/field-notes",
        json={**_VALID_PAYLOAD, **overrides},
        headers=auth_headers(user_id),
    )


def test_create_note_requires_authentication(client):
    response = client.post("/field-notes", json=_VALID_PAYLOAD)

    assert response.status_code == 401


def test_a_note_is_publicly_visible_the_moment_it_lands(client):
    response = _post_note(client, str(uuid.uuid4()))
    assert response.status_code == 201

    # Anonymous, no moderation step in between - §5's whole argument.
    listed = client.get("/field-notes")
    assert listed.status_code == 200
    assert [note["id"] for note in listed.json()] == [response.json()["id"]]


def test_create_note_is_idempotent_on_id(client, db_session):
    user_id = str(uuid.uuid4())
    note_id = str(uuid.uuid4())

    first = _post_note(client, user_id, id=note_id)
    second = _post_note(client, user_id, id=note_id)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == note_id
    assert db_session.query(FieldNote).count() == 1


def test_create_note_refuses_an_id_that_belongs_to_someone_else(client):
    note_id = str(uuid.uuid4())
    assert _post_note(client, str(uuid.uuid4()), id=note_id).status_code == 201

    response = _post_note(client, str(uuid.uuid4()), id=note_id)

    assert response.status_code == 409


def test_a_note_with_neither_tag_nor_text_is_refused(client):
    user_id = str(uuid.uuid4())

    silent = _post_note(client, user_id, observation=None, note=None)
    whitespace = _post_note(client, user_id, observation=None, note="   ")

    assert silent.status_code == 422
    assert whitespace.status_code == 422


def test_a_note_with_only_text_and_a_note_with_only_a_tag_are_both_fine(client):
    user_id = str(uuid.uuid4())

    text_only = _post_note(client, user_id, observation=None, note="Piped spring 0.4 mi north is running well.")
    tag_only = _post_note(client, user_id, note=None)

    assert text_only.status_code == 201
    assert tag_only.status_code == 201


def test_observed_at_is_the_hikers_claim_and_the_future_is_refused(client):
    user_id = str(uuid.uuid4())
    monday = datetime.now(timezone.utc) - timedelta(days=3)

    kept = _post_note(client, user_id, observed_at=monday.isoformat())
    future = _post_note(
        client,
        str(uuid.uuid4()),
        observed_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    )

    assert kept.status_code == 201
    stored = datetime.fromisoformat(kept.json()["observed_at"])
    assert abs((stored - monday).total_seconds()) < 5
    assert future.status_code == 422


def test_observed_at_falls_back_to_the_server_clock_when_absent(client):
    before = datetime.now(timezone.utc)
    response = _post_note(client, str(uuid.uuid4()))
    after = datetime.now(timezone.utc)

    stored = datetime.fromisoformat(response.json()["observed_at"])
    assert before - timedelta(seconds=5) <= stored <= after + timedelta(seconds=5)


def test_anonymous_readers_get_no_reporter_id_and_no_posted_at(client):
    author_id = str(uuid.uuid4())
    assert _post_note(client, author_id).status_code == 201

    note = client.get("/field-notes").json()[0]

    # Withheld, not absent: null is "not for you". reporter_type is the only
    # public attribution (§6).
    assert note["reporter_id"] is None
    assert note["posted_at"] is None
    assert note["reporter_type"] == "section"


def test_the_author_and_a_moderator_see_the_withheld_pair(client, db_session):
    author = make_profile(db_session, Role.hiker)
    moderator = make_profile(db_session, Role.maintainer)
    assert _post_note(client, author.id).status_code == 201

    own = client.get("/field-notes", headers=auth_headers(author.id)).json()[0]
    moderated = client.get("/field-notes", headers=auth_headers(moderator.id)).json()[0]
    strangers = client.get("/field-notes", headers=auth_headers(str(uuid.uuid4()))).json()[0]

    assert own["reporter_id"] == author.id
    assert moderated["reporter_id"] == author.id
    assert strangers["reporter_id"] is None


def test_poi_id_filter_returns_that_places_notes_newest_first(client):
    user_id = str(uuid.uuid4())
    monday = datetime.now(timezone.utc) - timedelta(days=3)
    tuesday = datetime.now(timezone.utc) - timedelta(days=2)
    assert _post_note(client, user_id, observed_at=monday.isoformat()).status_code == 201
    assert _post_note(client, user_id, observed_at=tuesday.isoformat(), observation="flowing").status_code == 201
    assert _post_note(client, user_id, poi_id="atc_shelters:elsewhere").status_code == 201

    listed = client.get("/field-notes", params={"poi_id": "atc_shelters:abc-123"}).json()

    assert [note["observation"] for note in listed] == ["flowing", "dry"]


def test_the_unfiltered_list_caps_each_place_at_its_most_recent_few(client):
    from app.routers.field_notes import NOTES_PER_POI

    user_id = str(uuid.uuid4())
    for days_ago in range(NOTES_PER_POI + 2):
        observed = datetime.now(timezone.utc) - timedelta(days=days_ago)
        assert (
            _post_note(client, user_id, id=str(uuid.uuid4()), observed_at=observed.isoformat()).status_code == 201
        )

    listed = client.get("/field-notes").json()

    assert len(listed) == NOTES_PER_POI
    # The survivors are the newest, in order.
    observed = [datetime.fromisoformat(note["observed_at"]) for note in listed]
    assert observed == sorted(observed, reverse=True)


def test_the_unfiltered_list_drops_notes_older_than_the_window(client):
    from app.routers.field_notes import NOTES_WINDOW_DAYS

    user_id = str(uuid.uuid4())
    stale = datetime.now(timezone.utc) - timedelta(days=NOTES_WINDOW_DAYS + 10)
    fresh = datetime.now(timezone.utc) - timedelta(days=1)
    assert _post_note(client, user_id, observed_at=stale.isoformat()).status_code == 201
    assert _post_note(client, user_id, observed_at=fresh.isoformat(), observation="flowing").status_code == 201

    listed = client.get("/field-notes").json()

    assert [note["observation"] for note in listed] == ["flowing"]
    # The old note is windowed out of the map's working set, not gone: the
    # card's per-place read still reaches it.
    card = client.get("/field-notes", params={"poi_id": "atc_shelters:abc-123"}).json()
    assert len(card) == 2


def test_flagging_requires_auth_and_counts_people_not_taps(client, db_session):
    author_id = str(uuid.uuid4())
    note_id = _post_note(client, author_id).json()["id"]
    flagger = str(uuid.uuid4())

    anonymous = client.post(f"/field-notes/{note_id}/flag", json={})
    first = client.post(
        f"/field-notes/{note_id}/flag", json={"reason": "spam"}, headers=auth_headers(flagger)
    )
    again = client.post(f"/field-notes/{note_id}/flag", json={}, headers=auth_headers(flagger))

    assert anonymous.status_code == 401
    assert first.status_code == 201
    assert again.status_code == 200
    assert db_session.query(NoteFlag).count() == 1


def test_the_note_queue_is_gated_to_moderator_roles(client):
    response = client.get("/moderation/field-notes", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 403


def test_hide_removes_a_note_from_every_public_read_and_unhide_restores_it(client, db_session):
    author = make_profile(db_session, Role.hiker)
    moderator = make_profile(db_session, Role.maintainer)
    note_id = _post_note(client, author.id).json()["id"]
    assert (
        client.post(f"/field-notes/{note_id}/flag", json={"reason": "abusive"}, headers=auth_headers(str(uuid.uuid4())))
        .status_code
        == 201
    )

    hidden = client.post(f"/field-notes/{note_id}/hide", headers=auth_headers(moderator.id))
    assert hidden.status_code == 200
    assert hidden.json()["hidden"] is True

    # Gone from the public list, the card read, and the AUTHOR's own read -
    # a hidden note has been removed by a person, and rendering it to its
    # author would show them a map nobody else sees.
    assert client.get("/field-notes").json() == []
    assert client.get("/field-notes", params={"poi_id": "atc_shelters:abc-123"}).json() == []
    assert client.get("/field-notes", headers=auth_headers(author.id)).json() == []
    # Flagging a hidden note answers exactly like flagging a missing one.
    assert (
        client.post(f"/field-notes/{note_id}/flag", json={}, headers=auth_headers(str(uuid.uuid4()))).status_code
        == 404
    )
    # The row survives - hidden, never deleted (§5).
    assert db_session.query(FieldNote).count() == 1

    restored = client.post(f"/field-notes/{note_id}/unhide", headers=auth_headers(moderator.id))
    assert restored.status_code == 200
    assert restored.json()["hidden"] is False
    assert [note["id"] for note in client.get("/field-notes").json()] == [note_id]


def test_hide_and_unhide_are_gated_to_moderator_roles(client):
    author_id = str(uuid.uuid4())
    note_id = _post_note(client, author_id).json()["id"]

    hide = client.post(f"/field-notes/{note_id}/hide", headers=auth_headers(str(uuid.uuid4())))
    unhide = client.post(f"/field-notes/{note_id}/unhide", headers=auth_headers(str(uuid.uuid4())))

    assert hide.status_code == 403
    assert unhide.status_code == 403


def test_the_queue_lists_flagged_work_first_and_hidden_notes_as_the_record(client, db_session):
    moderator = make_profile(db_session, Role.maintainer)
    author_id = str(uuid.uuid4())

    flagged_id = _post_note(client, author_id, id=str(uuid.uuid4())).json()["id"]
    hidden_id = _post_note(client, author_id, id=str(uuid.uuid4()), observation="flowing").json()["id"]
    unflagged_id = _post_note(client, author_id, id=str(uuid.uuid4()), observation="trickling").json()["id"]

    for flagger in (str(uuid.uuid4()), str(uuid.uuid4())):
        assert (
            client.post(f"/field-notes/{flagged_id}/flag", json={"reason": "wrong"}, headers=auth_headers(flagger))
            .status_code
            == 201
        )
    assert client.post(f"/field-notes/{hidden_id}/hide", headers=auth_headers(moderator.id)).status_code == 200

    queue = client.get("/moderation/field-notes", headers=auth_headers(moderator.id)).json()

    assert [entry["note"]["id"] for entry in queue] == [flagged_id, hidden_id]
    assert queue[0]["flag_count"] == 2
    assert queue[0]["reasons"] == ["wrong", "wrong"]
    assert queue[1]["hidden"] is True
    assert unflagged_id not in {entry["note"]["id"] for entry in queue}
    # The queue is the moderator surface, so the pattern-reading field rides
    # along - unlike every public read above.
    assert queue[0]["note"]["reporter_id"] == author_id
