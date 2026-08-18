"""Tests for the /hikes router, via the real FastAPI TestClient.

Mirrors tests/test_routers_profiles.py's token-minting pattern - real JWTs
signed with the same test-only SUPABASE_JWT_SECRET tests/conftest.py sets.
"""

import uuid

from tests.tokens import auth_headers


def test_create_hike_requires_authentication(client):
    response = client.post(
        "/hikes",
        json={"overall_start_reference": 0.0, "overall_end_reference": 2189.0},
    )

    assert response.status_code == 401


def test_get_hikes_only_returns_the_callers_own_hikes(client):
    user_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    user_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    create_a = client.post(
        "/hikes",
        json={"overall_start_reference": 0.0, "overall_end_reference": 2189.0},
        headers=auth_headers(user_a),
    )
    assert create_a.status_code == 201

    create_b = client.post(
        "/hikes",
        json={"overall_start_reference": 2189.0, "overall_end_reference": 0.0},
        headers=auth_headers(user_b),
    )
    assert create_b.status_code == 201

    response = client.get("/hikes", headers=auth_headers(user_a))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert all(hike["user_id"] == user_a for hike in body)


def test_get_hike_direction_endpoint_returns_nobo_for_a_springer_to_katahdin_hike(client):
    user_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

    create_response = client.post(
        "/hikes",
        json={"overall_start_reference": 0.0, "overall_end_reference": 2189.0},
        headers=auth_headers(user_id),
    )
    assert create_response.status_code == 201
    hike_id = create_response.json()["id"]

    response = client.get(f"/hikes/{hike_id}/direction", headers=auth_headers(user_id))

    assert response.status_code == 200
    assert response.json() == {"direction": "NOBO"}


def _create_hike(client, user_id):
    response = client.post(
        "/hikes",
        json={
            "overall_start_reference": 0.0,
            "overall_end_reference": 2189.0,
            "planned_start_date": "2027-03-01",
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_patch_with_an_explicit_null_on_a_non_nullable_field_is_a_422(client):
    """The 500 that #255 found, pinned as the 422 it should have been.

    `{"trail_id": null}` passes a bare `str | None` schema and then hits a
    `nullable=False` column as an IntegrityError. The schema now refuses it
    with an error naming the field.
    """
    user_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    hike_id = _create_hike(client, user_id)

    for field in ("trail_id", "overall_start_reference", "overall_end_reference"):
        response = client.patch(
            f"/hikes/{hike_id}",
            json={field: None},
            headers=auth_headers(user_id),
        )

        assert response.status_code == 422, field
        assert field in response.text


def test_patch_with_an_explicit_null_clears_planned_start_date(client):
    """The other half of the convention: null on a nullable field is a clear.

    A planned start date is exactly the kind of value that legitimately goes
    back to unknown - plans slip - so it must be removable, not only
    overwritable.
    """
    user_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    hike_id = _create_hike(client, user_id)

    response = client.patch(
        f"/hikes/{hike_id}",
        json={"planned_start_date": None},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    assert response.json()["planned_start_date"] is None


def test_patch_omitting_a_field_leaves_it_alone(client):
    user_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    hike_id = _create_hike(client, user_id)

    response = client.patch(
        f"/hikes/{hike_id}",
        json={"overall_end_reference": 1000.0},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overall_end_reference"] == 1000.0
    assert body["planned_start_date"] == "2027-03-01"
    assert body["trail_id"] == "AT"


# --- The single-hike endpoints (#322) ----------------------------------------
#
# GET/PATCH/DELETE /hikes/{id} had no tests at all, including the invariant
# _get_owned_hike_or_404's docstring states: someone else's hike 404s exactly
# like a missing one - never 403 - so this endpoint cannot be used to learn
# whether another user's hike id is valid.

OWNER = "dddddddd-dddd-dddd-dddd-dddddddddddd"
STRANGER = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"


def _created_hike_id(client, user_id=OWNER):
    response = client.post(
        "/hikes",
        json={"overall_start_reference": 0.0, "overall_end_reference": 2189.0},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_get_a_single_hike_returns_the_callers_own(client):
    hike_id = _created_hike_id(client)

    response = client.get(f"/hikes/{hike_id}", headers=auth_headers(OWNER))

    assert response.status_code == 200
    assert response.json()["id"] == hike_id


def test_someone_elses_hike_404s_exactly_like_a_missing_one(client):
    """The invariant, asserted through this router rather than only through
    /wrong-way-events' separate copy of the same check: a 403 would confirm
    the id exists, and confirming existence is the leak."""
    hike_id = _created_hike_id(client)

    as_stranger = client.get(f"/hikes/{hike_id}", headers=auth_headers(STRANGER))
    missing = client.get(f"/hikes/{uuid.uuid4()}", headers=auth_headers(STRANGER))

    assert as_stranger.status_code == 404, "someone else's hike must 404, never 403"
    assert as_stranger.status_code == missing.status_code
    assert as_stranger.json() == missing.json(), "the two answers must be indistinguishable"


def test_patch_someone_elses_hike_404s_and_changes_nothing(client):
    hike_id = _created_hike_id(client)

    response = client.patch(
        f"/hikes/{hike_id}",
        json={"overall_start_reference": 500.0},
        headers=auth_headers(STRANGER),
    )

    assert response.status_code == 404
    untouched = client.get(f"/hikes/{hike_id}", headers=auth_headers(OWNER))
    assert untouched.json()["overall_start_reference"] == 0.0


def test_delete_removes_the_callers_hike(client):
    hike_id = _created_hike_id(client)

    response = client.delete(f"/hikes/{hike_id}", headers=auth_headers(OWNER))

    assert response.status_code == 204
    assert client.get(f"/hikes/{hike_id}", headers=auth_headers(OWNER)).status_code == 404


def test_delete_someone_elses_hike_404s_and_the_hike_survives(client):
    hike_id = _created_hike_id(client)

    response = client.delete(f"/hikes/{hike_id}", headers=auth_headers(STRANGER))

    assert response.status_code == 404
    assert client.get(f"/hikes/{hike_id}", headers=auth_headers(OWNER)).status_code == 200
