from datetime import UTC, datetime, timedelta

import pytest
from conftest import bearer
from sqlalchemy import update

from steward_api import limits
from steward_api.models import Claim

SITE = "4d9ce529-d198-40ee-9a11-02b0184b5270"
NEIGHBOUR = "f599a2a9-c5c4-4e62-c303-2ebb43e75017"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 200 + b"\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG_WITH_EXIF = b"\xff\xd8\xff\xe1\x00\x16Exif\x00\x00MM\x00*" + b"\x00" * 200 + b"\xff\xd9"


def claim(client, who="claimer", sites=(SITE,)):
    response = client.post("/claims", json={"rims_ids": list(sites)}, headers=bearer(who))
    assert response.status_code == 201, response.text
    return response.json()[0]["id"]


def photo(client, claim_id, phase, point=None, who="claimer", body=JPEG):
    params = {"phase": phase} | ({"point": point} if point is not None else {})
    return client.post(
        f"/claims/{claim_id}/photos", params=params, content=body, headers={**bearer(who), "Content-Type": "image/jpeg"}
    )


def photograph_everything(client, claim_id, who="claimer"):
    for point in limits.PHOTO_POINTS:
        for phase in ("before", "after"):
            assert photo(client, claim_id, phase, point, who).status_code == 201


def overdue(app, claim_id):
    with app.state.sessionmaker() as db:
        db.execute(update(Claim).where(Claim.id == claim_id).values(due_at=datetime.now(UTC) - timedelta(minutes=1)))
        db.commit()


def test_a_claim_lasts_fourteen_days_and_holds_the_site_against_a_second_claim(client):
    claim_id = claim(client)
    detail = client.get(f"/claims/{claim_id}", headers=bearer("claimer")).json()
    claimed, due = (datetime.fromisoformat(detail[k]) for k in ("claimed_at", "due_at"))
    assert due - claimed == timedelta(days=limits.CLAIM_DAYS)
    assert detail["state"] == "claimed" and detail["you_are_crew"] is True
    second = client.post("/claims", json={"rims_ids": [SITE]}, headers=bearer("someone-else"))
    assert second.status_code == 409 and SITE in second.json()["detail"]


def test_claiming_a_cluster_is_all_or_nothing(client):
    claim(client, who="first", sites=(NEIGHBOUR,))
    both = client.post("/claims", json={"rims_ids": [SITE, NEIGHBOUR]}, headers=bearer("second"))
    assert both.status_code == 409
    assert client.get(f"/claims/site/{SITE}", headers=bearer("second")).json() is None


def test_a_claim_past_its_due_time_is_released_and_the_site_can_be_claimed_again(client, app):
    claim_id = claim(client)
    overdue(app, claim_id)
    assert client.get(f"/claims/site/{SITE}", headers=bearer("anyone")).json() is None
    assert client.get(f"/claims/{claim_id}", headers=bearer("claimer")).json()["state"] == "released"
    claim(client, who="next-volunteer")


def test_only_the_claimer_can_release_and_releasing_opens_the_site(client):
    claim_id = claim(client)
    assert client.post(f"/claims/{claim_id}/release", headers=bearer("stranger")).status_code == 403
    assert client.post(f"/claims/{claim_id}/release", headers=bearer("claimer")).json()["state"] == "released"
    assert client.get(f"/claims/site/{SITE}", headers=bearer("anyone")).json() is None


def test_an_invite_link_adds_whoever_opens_it_to_the_crew_and_a_new_link_ends_the_old(client):
    claim_id = claim(client)
    first = client.post(f"/claims/{claim_id}/invite", headers=bearer("claimer")).json()["token"]
    assert client.post("/claims/join", json={"token": first}, headers=bearer("friend")).json()["you_are_crew"] is True
    second = client.post(f"/claims/{claim_id}/invite", headers=bearer("friend")).json()["token"]
    assert client.post("/claims/join", json={"token": first}, headers=bearer("late")).status_code == 404
    assert client.post("/claims/join", json={"token": second}, headers=bearer("late")).status_code == 200
    assert client.get(f"/claims/{claim_id}", headers=bearer("claimer")).json()["crew_size"] == 3


def test_someone_off_the_crew_cannot_photograph_invite_log_hours_or_submit(client):
    claim_id = claim(client)
    stranger = bearer("stranger")
    assert photo(client, claim_id, "before", 1, who="stranger").status_code == 403
    assert client.post(f"/claims/{claim_id}/invite", headers=stranger).status_code == 403
    assert client.put(f"/claims/{claim_id}/hours", json={"hours": 2}, headers=stranger).status_code == 403
    assert client.post(f"/claims/{claim_id}/submit", json={}, headers=stranger).status_code == 403


def test_the_first_before_photo_starts_the_work_and_a_new_photo_replaces_the_old_at_its_point(client, app):
    claim_id = claim(client)
    assert photo(client, claim_id, "before", 1).json()["state"] == "in_progress"
    detail = photo(client, claim_id, "before", 1, body=PNG).json()
    assert [(p["phase"], p["point"]) for p in detail["photos"]] == [("before", 1)]
    assert len(app.state.photos.objects) == 1
    assert detail["photos"][0]["url"].startswith("memory://claims/")


@pytest.mark.parametrize(
    ("params", "body", "status"),
    [
        ({"phase": "before"}, JPEG, 422),
        ({"phase": "before", "point": 3}, JPEG, 422),
        ({"phase": "extra", "point": 1}, JPEG, 422),
        ({"phase": "before", "point": 1}, b"<svg onload=alert(1)>", 415),
        ({"phase": "before", "point": 1}, b"GIF89a" + b"\x00" * 50, 415),
        ({"phase": "before", "point": 1}, JPEG_WITH_EXIF, 422),
    ],
)
def test_a_photo_that_is_not_one_of_the_accepted_kinds_is_refused(client, app, params, body, status):
    claim_id = claim(client)
    response = client.post(
        f"/claims/{claim_id}/photos", params=params, content=body, headers={**bearer("claimer"), "Content-Type": "image/jpeg"}
    )
    assert response.status_code == status
    assert app.state.photos.objects == {}


def test_a_photo_past_the_size_cap_is_refused(client, monkeypatch):
    monkeypatch.setattr(limits, "PHOTO_MAX_BYTES", 1000)
    claim_id = claim(client)
    assert photo(client, claim_id, "before", 1, body=JPEG + b"\x00" * 2000).status_code == 413


def test_photo_uploads_say_so_when_no_bucket_is_set_up(client, app):
    claim_id = claim(client)
    app.state.photos = None
    response = photo(client, claim_id, "before", 1)
    assert response.status_code == 503 and "not set up" in response.json()["detail"]


def test_submitting_needs_both_photo_points_before_and_after(client):
    claim_id = claim(client)
    photo(client, claim_id, "before", 1)
    response = client.post(f"/claims/{claim_id}/submit", json={"steps_done": ["Hide the site"]}, headers=bearer("claimer"))
    assert response.status_code == 422
    assert "after at point 1" in response.json()["detail"] and "before at point 2" in response.json()["detail"]


def submitted(client, who="claimer"):
    claim_id = claim(client, who=who)
    photograph_everything(client, claim_id, who)
    client.put(f"/claims/{claim_id}/hours", json={"hours": 2.5}, headers=bearer(who))
    response = client.post(
        f"/claims/{claim_id}/submit",
        json={"steps_done": ["Hide the site", "Block the way in"], "notes": "Done"},
        headers=bearer(who),
    )
    assert response.status_code == 200, response.text
    return claim_id


def test_a_submission_stops_the_clock_so_a_slow_reviewer_never_costs_the_claim(client, app):
    claim_id = submitted(client)
    overdue(app, claim_id)
    assert client.get(f"/claims/{claim_id}", headers=bearer("claimer")).json()["state"] == "submitted"


def test_nobody_on_the_crew_can_review_their_own_submission(client):
    claim_id = claim(client)
    token = client.post(f"/claims/{claim_id}/invite", headers=bearer("claimer")).json()["token"]
    client.post("/claims/join", json={"token": token}, headers=bearer("crewmate"))
    photograph_everything(client, claim_id)
    client.post(f"/claims/{claim_id}/submit", json={}, headers=bearer("claimer"))
    for crew in ("claimer", "crewmate"):
        assert client.post(f"/claims/{claim_id}/review", json={"verdict": "verify"}, headers=bearer(crew)).status_code == 403
        assert claim_id not in [c["id"] for c in client.get("/reviews", headers=bearer(crew)).json()]


def test_verifying_confirms_the_crew_s_hours(client):
    claim_id = submitted(client)
    assert [c["id"] for c in client.get("/reviews", headers=bearer("reviewer")).json()] == [claim_id]
    verdict = client.post(f"/claims/{claim_id}/review", json={"verdict": "verify"}, headers=bearer("reviewer")).json()
    assert verdict["state"] == "verified"
    assert client.get("/hours/mine", headers=bearer("claimer")).json() == {"verified": 2.5, "waiting": 0.0, "claims": 1}


def test_sending_back_needs_a_reason_and_gives_the_crew_more_days(client):
    claim_id = submitted(client)
    assert client.post(f"/claims/{claim_id}/review", json={"verdict": "send_back"}, headers=bearer("reviewer")).status_code == 422
    sent = client.post(
        f"/claims/{claim_id}/review",
        json={"verdict": "send_back", "note": "Point 2's after photo is blurred"},
        headers=bearer("reviewer"),
    ).json()
    assert sent["state"] == "in_progress" and sent["review_note"] == "Point 2's after photo is blurred"
    remaining = datetime.fromisoformat(sent["due_at"]) - datetime.now(UTC)
    assert timedelta(days=limits.SEND_BACK_DAYS - 1) < remaining <= timedelta(days=limits.SEND_BACK_DAYS)


def test_hours_are_in_half_hours_and_bounded(client):
    claim_id = claim(client)
    for bad in (0, -1, 0.3, limits.HOURS_MAX + 1):
        assert client.put(f"/claims/{claim_id}/hours", json={"hours": bad}, headers=bearer("claimer")).status_code == 422


def test_one_account_works_on_at_most_the_live_claim_limit(client, monkeypatch):
    monkeypatch.setattr(limits, "LIVE_CLAIMS_PER_USER", 1)
    claim(client)
    assert client.post("/claims", json={"rims_ids": [NEIGHBOUR]}, headers=bearer("claimer")).status_code == 409


def test_deleting_an_account_releases_the_claims_it_was_working_on(client):
    claim_id = claim(client)
    assert client.delete("/me", headers=bearer("claimer")).status_code == 204
    detail = client.get(f"/claims/{claim_id}", headers=bearer("anyone")).json()
    assert detail["state"] == "released" and detail["claimer"] is None and detail["crew"] == []
