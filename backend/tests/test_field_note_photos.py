"""A field note's photo: publish-now, screened on the phone, held only for
nudity and only until one person looks (#879).

The maintainer's 2026-08-21 decision is the thing these cases hold to.
DATA_NUDGES.md's opted-in mode has promised "a photo becomes the default,
not the escalation" since July, and #759 shipped without it because nobody
had decided whether a note photo publishes with its note or waits like a
report photo. It publishes.

What makes that defensible is not the on-device screen - #837 decided the
screen flags and never decides - it is the narrow hold behind the one
finding that needs one, and the human glance that ends it. So:

  - **The photo is the author's claim.** Nobody else can put bytes under
    somebody's note; that would be a fabrication with a real person's
    reporter_type on it.
  - **Nudity holds, faces do not.** Exactly the waypoint gallery's rule
    (poi_photos.py's `_held`), because it is the same check feeding both and
    a second rule for one mechanism is how the two drift apart.
  - **A held photo is invisible rather than announced.** A public reader
    gets a note with no photo and no hint that one is waiting.
  - **Nothing costs the sentence.** A photo that will not upload, a server
    with no bucket, a note hidden by a moderator - the note itself still
    reads, or is gone entirely, and never half of each.

S3 is doubled in-process with moto, test_poi_photos.py's convention.
"""

import uuid

import boto3
import pytest
from moto import mock_aws

from app.config import settings
from app.core.photos import note_photo_key
from app.models.field_note import FieldNote
from app.models.profile import Role
from tests.factories import make_profile
from tests.tokens import auth_headers

_BUCKET = "ourhike-test"
_JPEG = b"\xff\xd8\xff\xe0" + b"pretend jpeg bytes" * 4
_POI = "atc_shelters:abc123"


@pytest.fixture()
def r2(monkeypatch):
    """A configured, empty bucket with uploads on - test_poi_photos.py's."""
    with mock_aws():
        monkeypatch.setattr(settings, "r2_photo_endpoint_url", "https://s3.amazonaws.com")
        monkeypatch.setattr(settings, "r2_photo_bucket", _BUCKET)
        monkeypatch.setattr(settings, "r2_photo_access_key_id", "test-key")
        monkeypatch.setattr(settings, "r2_photo_secret_access_key", "test-secret")
        monkeypatch.setattr(settings, "r2_photo_write_enabled", True)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=_BUCKET)
        yield s3


def _file_note(client, author_id: str, *, flagged: str | None = None) -> str:
    note_id = str(uuid.uuid4())
    payload = {
        "id": note_id,
        "poi_id": _POI,
        "observation": "dry",
        "reporter_type": "thru",
        **({"photo_flagged": flagged} if flagged is not None else {}),
    }
    response = client.post("/field-notes", json=payload, headers=auth_headers(author_id))
    assert response.status_code == 201, response.text
    return note_id


def _upload(client, note_id: str, author_id: str, body: bytes = _JPEG):
    return client.put(
        f"/field-notes/{note_id}/photo",
        content=body,
        headers={**auth_headers(author_id), "Content-Type": "image/jpeg"},
    )


def _public_note(client, note_id: str) -> dict:
    """The note as an anonymous reader sees it - which is the audience the
    hold exists for."""
    response = client.get(f"/field-notes?poi_id={_POI}")
    assert response.status_code == 200
    return next(note for note in response.json() if note["id"] == note_id)


def test_the_author_uploads_the_bytes_and_the_photo_appears(client, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author)

    response = _upload(client, note_id, author)

    assert response.status_code == 200
    assert response.json()["photo_url"] is not None
    # The object really landed, at the key derived from the NOTE - see
    # core/photos.py for why not the community store's contributor key.
    assert r2.get_object(Bucket=_BUCKET, Key=note_photo_key(note_id))["Body"].read() == _JPEG


def test_somebody_else_cannot_put_bytes_under_your_note(client, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author)

    response = _upload(client, note_id, str(uuid.uuid4()))

    # 403 rather than 404: the note is public, and pretending it does not
    # exist would be a lie about a row the caller can already read.
    assert response.status_code == 403


def test_a_photo_publishes_with_its_note(client, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author)
    _upload(client, note_id, author)

    # No cooling-off, unlike a community share: the note is the unit, and a
    # picture appearing two hours after the sentence it belongs to would be a
    # card that changes its story while a hiker reads it.
    assert _public_note(client, note_id)["photo_url"] is not None


def test_a_nudity_flag_holds_the_photo_from_the_public(client, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author, flagged="nudity")
    _upload(client, note_id, author)

    public = _public_note(client, note_id)

    assert public["photo_url"] is None
    # And no hint that anything is behind it. "There is a held photo here" is
    # a sentence only the author and a moderator have any use for.
    assert public["photo_held"] is False
    # The NOTE still publishes. Freshness is the whole feature, and it is
    # never what waits.
    assert public["observation"] == "dry"


def test_the_author_and_a_moderator_still_see_a_held_photo(client, db_session, r2):
    author = make_profile(db_session, Role.hiker)
    note_id = _file_note(client, author.id, flagged="nudity")
    _upload(client, note_id, author.id)
    moderator = make_profile(db_session, Role.maintainer)

    for viewer in (author.id, moderator.id):
        response = client.get(f"/field-notes?poi_id={_POI}", headers=auth_headers(viewer))
        note = next(row for row in response.json() if row["id"] == note_id)
        # The author because it is theirs; the moderator because LOOKING is
        # the review the hold is waiting for.
        assert note["photo_url"] is not None, viewer
        assert note["photo_held"] is True, viewer


def test_a_face_flag_does_not_hold_anything(client, r2):
    """poi_photos.py's `_held` reaches only the nudity case, and this is the
    same check feeding both surfaces. A face flag orders the queue."""
    author = str(uuid.uuid4())
    note_id = _file_note(client, author, flagged="faces")
    _upload(client, note_id, author)

    assert _public_note(client, note_id)["photo_url"] is not None


def test_one_human_glance_releases_the_hold(client, db_session, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author, flagged="nudity")
    _upload(client, note_id, author)
    moderator = make_profile(db_session, Role.maintainer)

    response = client.post(f"/field-notes/{note_id}/photo/review", headers=auth_headers(moderator.id))

    assert response.status_code == 200
    assert _public_note(client, note_id)["photo_url"] is not None


def test_reviewing_twice_keeps_who_looked_first(client, db_session, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author, flagged="nudity")
    _upload(client, note_id, author)
    first = make_profile(db_session, Role.maintainer)
    second = make_profile(db_session, Role.maintainer)

    client.post(f"/field-notes/{note_id}/photo/review", headers=auth_headers(first.id))
    client.post(f"/field-notes/{note_id}/photo/review", headers=auth_headers(second.id))

    # Who FIRST cleared it is the fact an audit needs - moderation.py's rule
    # for every grant in this codebase.
    db_session.expire_all()
    assert db_session.get(FieldNote, note_id).photo_reviewed_by == first.id


def test_a_hiker_cannot_release_their_own_hold(client, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author, flagged="nudity")
    _upload(client, note_id, author)

    response = client.post(f"/field-notes/{note_id}/photo/review", headers=auth_headers(author))

    assert response.status_code == 403


def test_a_hidden_note_takes_its_photo_with_it(client, db_session, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author)
    _upload(client, note_id, author)
    moderator = make_profile(db_session, Role.maintainer)

    client.post(f"/field-notes/{note_id}/hide", headers=auth_headers(moderator.id))

    # The takedown path, and it needs no photo-specific verb: a note whose
    # photo was the problem is a note somebody wrote to carry that photo.
    assert all(row["id"] != note_id for row in client.get(f"/field-notes?poi_id={_POI}").json())


def test_bytes_that_are_not_a_jpeg_are_refused_by_their_own_magic(client, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author)

    response = _upload(client, note_id, author, body=b"GIF89a not a jpeg at all")

    # #379's rule: decided by the bytes rather than by a header the client
    # writes, because the header is the part an attacker controls for free.
    assert response.status_code == 415


def test_an_empty_body_is_refused_rather_than_stored(client, r2):
    author = str(uuid.uuid4())
    note_id = _file_note(client, author)

    assert _upload(client, note_id, author, body=b"").status_code == 400


def test_a_server_with_no_bucket_says_so_and_keeps_the_note(client):
    """No `r2` fixture: photo storage is not configured at all.

    The note has already landed by then - the two-phase flush is what makes
    that true - so what a hiker loses is the picture and never the sentence
    about the spring.
    """
    author = str(uuid.uuid4())
    note_id = _file_note(client, author)

    response = _upload(client, note_id, author)

    assert response.status_code == 503
    assert _public_note(client, note_id)["observation"] == "dry"
    assert _public_note(client, note_id)["photo_url"] is None
