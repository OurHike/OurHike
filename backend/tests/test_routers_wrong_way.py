"""Tests for the `/wrong-way-events` router.

See ../../features/HIKER_SAFETY.md §5. The actual off-trail/wrong-direction
DETECTION is pure client-side geometry over a live GPS trace (an ephemeral
`WrongWayCheck` that is never persisted here). This endpoint's only job is
receiving a "sustained divergence confirmed" event once the client's own
detection logic decides to escalate, verifying the referenced hike actually
belongs to the caller, and accepting it. Real push delivery (APNs/FCM) is
explicitly out of scope - this endpoint's job ends at "accepted the event".
"""

import uuid

from app.models.hike import Hike
from app.models.profile import Profile, Role
from tests.tokens import auth_headers


def test_post_wrong_way_event_requires_authentication(client, db_session):
    owner_id = str(uuid.uuid4())
    owner = Profile(id=owner_id, role=Role.hiker)
    db_session.add(owner)
    db_session.commit()
    hike = Hike(user_id=owner_id, overall_start_reference=0.0, overall_end_reference=2189.0)
    db_session.add(hike)
    db_session.commit()

    response = client.post("/wrong-way-events", json={"hike_id": hike.id})

    assert response.status_code == 401


def test_post_wrong_way_event_rejects_a_hike_that_does_not_belong_to_the_caller(client, db_session):
    owner_id = str(uuid.uuid4())
    owner = Profile(id=owner_id, role=Role.hiker)
    other_id = str(uuid.uuid4())
    other = Profile(id=other_id, role=Role.hiker)
    db_session.add_all([owner, other])
    db_session.commit()
    hike = Hike(user_id=owner_id, overall_start_reference=0.0, overall_end_reference=2189.0)
    db_session.add(hike)
    db_session.commit()

    response = client.post(
        "/wrong-way-events",
        json={"hike_id": hike.id},
        headers=auth_headers(other_id),
    )

    # 404, not 403 - matching hikes.py's existing "don't leak id validity to
    # a non-owner" convention (see app/routers/hikes.py).
    assert response.status_code == 404


def test_post_wrong_way_event_accepts_a_valid_event_for_the_callers_own_hike(client, db_session):
    owner_id = str(uuid.uuid4())
    owner = Profile(id=owner_id, role=Role.hiker)
    db_session.add(owner)
    db_session.commit()
    hike = Hike(user_id=owner_id, overall_start_reference=0.0, overall_end_reference=2189.0)
    db_session.add(hike)
    db_session.commit()

    response = client.post(
        "/wrong-way-events",
        json={"hike_id": hike.id},
        headers=auth_headers(owner_id),
    )

    assert response.status_code == 202
    assert response.json()["received"] is True
