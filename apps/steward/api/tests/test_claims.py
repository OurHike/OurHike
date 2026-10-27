from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from conftest import NEIGHBOUR, SCORES_WELL, SITE, bearer, image
from PIL import Image
from sqlalchemy import update

from steward_api import limits
from steward_api.models import Claim

JPEG = image("JPEG")
PNG = image("PNG")


def claim(client, who="claimer", sites=(SITE,)):
    response = client.post("/claims", json={"rims_ids": list(sites)}, headers=bearer(who))
    assert response.status_code == 201, response.text
    return response.json()[0]["id"]


def photo(client, claim_id, phase, point=None, who="claimer", body=JPEG):
    params = {"phase": phase} | ({"point": point} if point is not None else {})
    return client.post(
        f"/claims/{claim_id}/photos", params=params, content=body, headers={**bearer(who), "Content-Type": "image/jpeg"}
    )


def photograph(client, claim_id, phases=("before", "after"), who="claimer"):
    for point in limits.PHOTO_POINTS:
        for phase in phases:
            assert photo(client, claim_id, phase, point, who).status_code == 201


def overdue(app, claim_id):
    with app.state.sessionmaker() as db:
        db.execute(update(Claim).where(Claim.id == claim_id).values(due_at=datetime.now(UTC) - timedelta(minutes=1)))
        db.commit()


def submitted(client, who="claimer", site=SITE):
    claim_id = claim(client, who=who, sites=(site,))
    photograph(client, claim_id, who=who)
    client.put(f"/claims/{claim_id}/hours", json={"hours": 2.5}, headers=bearer(who))
    response = client.post(
        f"/claims/{claim_id}/submit",
        json={"steps_done": ["Hide the site", "Block the way in"], "notes": "Done"},
        headers=bearer(who),
    )
    assert response.status_code == 200, response.text
    return claim_id


# --- Claiming -----------------------------------------------------------------------


def test_a_claim_lasts_fourteen_days_and_holds_the_site_against_a_second_claim(client):
    claim_id = claim(client)
    detail = client.get(f"/claims/{claim_id}", headers=bearer("claimer")).json()
    claimed, due = (datetime.fromisoformat(detail[k]) for k in ("claimed_at", "due_at"))
    assert due - claimed == timedelta(days=limits.CLAIM_DAYS)
    assert detail["state"] == "claimed" and detail["you_are_crew"] is True
    second = client.post("/claims", json={"rims_ids": [SITE]}, headers=bearer("someone-else"))
    assert second.status_code == 409 and SITE in second.json()["detail"]


@pytest.mark.parametrize("site", [SCORES_WELL, "00000000-0000-0000-0000-000000000000"])
def test_only_a_site_the_analysis_says_needs_work_can_be_claimed(client, site):
    response = client.post("/claims", json={"rims_ids": [site]}, headers=bearer("claimer"))
    assert response.status_code == 422 and site in response.json()["detail"]


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


def test_the_hold_limit_counts_sites_waiting_for_review_since_they_still_hold_the_site(client, monkeypatch):
    # The adversarial review (finding 2) held 30 sites with a cap of 10 by
    # submitting each claim, because the cap counted only open claims.
    monkeypatch.setattr(limits, "LIVE_CLAIMS_PER_USER", 1)
    submitted(client)
    assert client.post("/claims", json={"rims_ids": [NEIGHBOUR]}, headers=bearer("claimer")).status_code == 409


# --- The crew ---------------------------------------------------------------------


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


# --- Photos -----------------------------------------------------------------------


def test_the_first_before_photo_starts_the_work_and_a_new_photo_replaces_the_old_at_its_point(client, app):
    claim_id = claim(client)
    assert photo(client, claim_id, "before", 1).json()["state"] == "in_progress"
    detail = photo(client, claim_id, "before", 1, body=PNG).json()
    assert [(p["phase"], p["point"]) for p in detail["photos"]] == [("before", 1)]
    assert len(app.state.photos.objects) == 1
    assert detail["photos"][0]["url"].startswith("memory://claims/")


def stored(app) -> Image.Image:
    [(body, content_type)] = app.state.photos.objects.values()
    assert content_type == "image/jpeg"
    return Image.open(BytesIO(body))


def gps_exif() -> Image.Exif:
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (44.0, 30.0, 0.0), 3: "W", 4: (71.0, 15.0, 0.0)}  # GPSInfo
    exif[0x0110] = "Example phone"  # Model
    return exif


@pytest.mark.parametrize(
    "upload",
    [
        image("JPEG", exif=gps_exif()),
        image("PNG", exif=gps_exif()),
        image("WEBP", exif=gps_exif()),
        image("JPEG", xmp=b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><exif:GPSLatitude>44,30N</exif:GPSLatitude></x:xmpmeta>'),
    ],
    ids=["jpeg-exif", "png-exif", "webp-exif", "jpeg-xmp"],
)
def test_every_photo_is_redrawn_as_a_jpeg_with_no_metadata_at_all(client, app, upload):
    # The review's finding 6 got past a byte search for EXIF four ways; these
    # are its cases. Whatever arrives, only its pixels are kept.
    claim_id = claim(client)
    assert photo(client, claim_id, "before", 1, body=upload).status_code == 201
    kept = stored(app)
    assert kept.format == "JPEG"
    assert dict(kept.getexif()) == {}
    assert not {"exif", "xmp", "XML:com.adobe.xmp", "icc_profile"} & set(kept.info)


def test_a_large_photo_is_shrunk_to_the_long_side_limit(client, app, monkeypatch):
    monkeypatch.setattr(limits, "PHOTO_LONG_SIDE", 32)
    claim_id = claim(client)
    photo(client, claim_id, "before", 1, body=image("JPEG", size=(128, 96)))
    assert stored(app).size == (32, 24)


@pytest.mark.parametrize(
    ("params", "body", "status"),
    [
        ({"phase": "before"}, JPEG, 422),
        ({"phase": "before", "point": 3}, JPEG, 422),
        ({"phase": "extra", "point": 1}, JPEG, 422),
        ({"phase": "before", "point": 1}, b"<svg onload=alert(1)>", 415),
        ({"phase": "before", "point": 1}, image("GIF"), 415),
        ({"phase": "before", "point": 1}, b"\xff\xd8\xff<html><script>alert(1)</script></html>", 415),
    ],
    ids=["no-point", "point-3", "extra-with-point", "svg", "gif", "html-behind-a-jpeg-header"],
)
def test_a_photo_that_is_not_one_of_the_accepted_kinds_is_refused(client, app, params, body, status):
    claim_id = claim(client)
    response = client.post(
        f"/claims/{claim_id}/photos", params=params, content=body, headers={**bearer("claimer"), "Content-Type": "image/jpeg"}
    )
    assert response.status_code == status
    assert app.state.photos.objects == {}


def test_a_photo_claiming_more_pixels_than_any_camera_is_refused_unread(client, app, monkeypatch):
    monkeypatch.setattr(limits, "PHOTO_MAX_PIXELS", 1000)
    claim_id = claim(client)
    assert photo(client, claim_id, "before", 1, body=image("PNG", size=(100, 100))).status_code == 415
    assert app.state.photos.objects == {}


def test_a_photo_past_the_size_cap_is_refused(client, monkeypatch):
    monkeypatch.setattr(limits, "PHOTO_MAX_BYTES", 1000)
    claim_id = claim(client)
    assert photo(client, claim_id, "before", 1, body=JPEG + b"\x00" * 2000).status_code == 413


def test_an_upload_from_off_the_crew_is_refused_before_its_body_is_read(client, monkeypatch):
    # Authorization first: before the review's finding 1, a stranger's upload
    # was read in full, holding a database connection, before anything was checked.
    monkeypatch.setattr(limits, "PHOTO_MAX_BYTES", 1000)
    claim_id = claim(client)
    assert photo(client, claim_id, "before", 1, who="stranger", body=b"\x00" * 5000).status_code == 403


def test_signing_in_returns_the_database_connection_before_the_handler_runs(client, app):
    # current_user ends its transaction, so an upload streaming its body holds
    # no connection (the review's finding 1 emptied the pool with 15 slow uploads).
    from fastapi import Depends

    from steward_api.auth import current_user

    seen = {}

    @app.get("/test-connections-held")
    def held(user=Depends(current_user)):
        seen["checked_out"] = app.state.engine.pool.checkedout()
        return {}

    assert client.get("/test-connections-held", headers=bearer("a")).status_code == 200
    assert seen["checked_out"] == 0


def test_photo_uploads_say_so_when_no_bucket_is_set_up(client, app):
    claim_id = claim(client)
    app.state.photos = None
    response = photo(client, claim_id, "before", 1)
    assert response.status_code == 503 and "not set up" in response.json()["detail"]


# --- Submitting and reviewing -----------------------------------------------------------


def test_submitting_needs_both_photo_points_before_and_after(client):
    claim_id = claim(client)
    photo(client, claim_id, "before", 1)
    response = client.post(f"/claims/{claim_id}/submit", json={"steps_done": ["Hide the site"]}, headers=bearer("claimer"))
    assert response.status_code == 422
    assert "after at point 1" in response.json()["detail"] and "before at point 2" in response.json()["detail"]


def test_a_submission_stops_the_clock_so_a_slow_reviewer_never_costs_the_claim(client, app):
    claim_id = submitted(client)
    overdue(app, claim_id)
    assert client.get(f"/claims/{claim_id}", headers=bearer("claimer")).json()["state"] == "submitted"


def test_nobody_on_the_crew_can_review_their_own_submission(client):
    claim_id = claim(client)
    token = client.post(f"/claims/{claim_id}/invite", headers=bearer("claimer")).json()["token"]
    client.post("/claims/join", json={"token": token}, headers=bearer("crewmate"))
    photograph(client, claim_id)
    client.post(f"/claims/{claim_id}/submit", json={}, headers=bearer("claimer"))
    for crew in ("claimer", "crewmate"):
        assert client.post(f"/claims/{claim_id}/review", json={"verdict": "verify"}, headers=bearer(crew)).status_code == 403
        assert claim_id not in [c["id"] for c in client.get("/reviews", headers=bearer(crew)).json()]


def test_deleting_an_account_does_not_make_its_own_work_reviewable_by_it(client):
    # The review's finding 3: DELETE /me, then the same token verified its own claim.
    claim_id = submitted(client)
    assert client.delete("/me", headers=bearer("claimer")).status_code == 204
    response = client.post(f"/claims/{claim_id}/review", json={"verdict": "verify"}, headers=bearer("claimer"))
    assert response.status_code == 401
    assert client.get(f"/claims/{claim_id}", headers=bearer("anyone")).json()["state"] == "submitted"


def test_verifying_confirms_the_crew_s_hours_and_keeps_the_reviewer_s_name_as_it_was(client):
    claim_id = submitted(client)
    client.patch("/me", json={"display_name": "Careful Reviewer"}, headers=bearer("reviewer"))
    assert [c["id"] for c in client.get("/reviews", headers=bearer("reviewer")).json()] == [claim_id]
    verdict = client.post(f"/claims/{claim_id}/review", json={"verdict": "verify"}, headers=bearer("reviewer")).json()
    assert verdict["state"] == "verified" and verdict["reviewed_by"] == "Careful Reviewer"
    assert client.get("/hours/mine", headers=bearer("claimer")).json() == {"verified": 2.5, "waiting": 0.0, "claims": 1}
    client.patch("/me", json={"display_name": "Someone Else Entirely"}, headers=bearer("reviewer"))
    assert client.get(f"/claims/{claim_id}", headers=bearer("x")).json()["reviewed_by"] == "Careful Reviewer"


@pytest.mark.parametrize("verdict", ["send_back", "reject"])
def test_sending_back_or_rejecting_needs_a_reason(client, verdict):
    claim_id = submitted(client)
    assert client.post(f"/claims/{claim_id}/review", json={"verdict": verdict}, headers=bearer("reviewer")).status_code == 422


def test_a_send_back_gives_the_crew_back_the_time_it_had_left_and_at_least_the_minimum(client, app):
    # The review's finding 9: a send-back used to set seven days whatever was
    # left, so any reviewer could shorten a crew's clock.
    claim_id = submitted(client)
    sent = client.post(
        f"/claims/{claim_id}/review", json={"verdict": "send_back", "note": "Point 2 is blurred"}, headers=bearer("reviewer")
    ).json()
    assert sent["state"] == "in_progress" and sent["review_note"] == "Point 2 is blurred"
    remaining = datetime.fromisoformat(sent["due_at"]) - datetime.now(UTC)
    assert timedelta(days=limits.CLAIM_DAYS - 1) < remaining <= timedelta(days=limits.CLAIM_DAYS)

    # With a day left at submission, the minimum applies instead.
    other = submitted(client, who="late-crew", site=NEIGHBOUR)
    with app.state.sessionmaker() as db:
        db.execute(update(Claim).where(Claim.id == other).values(due_at=Claim.submitted_at + timedelta(days=1)))
        db.commit()
    late = client.post(
        f"/claims/{other}/review", json={"verdict": "send_back", "note": "Retake"}, headers=bearer("reviewer")
    ).json()
    remaining = datetime.fromisoformat(late["due_at"]) - datetime.now(UTC)
    assert timedelta(days=limits.SEND_BACK_DAYS - 1) < remaining <= timedelta(days=limits.SEND_BACK_DAYS)


def test_after_a_send_back_the_after_photos_must_be_retaken(client):
    claim_id = submitted(client)
    client.post(f"/claims/{claim_id}/review", json={"verdict": "send_back", "note": "Not hidden yet"}, headers=bearer("reviewer"))
    again = client.post(f"/claims/{claim_id}/submit", json={}, headers=bearer("claimer"))
    assert again.status_code == 422 and "retaken" in again.json()["detail"]
    photograph(client, claim_id, phases=("after",))
    assert client.post(f"/claims/{claim_id}/submit", json={}, headers=bearer("claimer")).json()["state"] == "submitted"


def test_rejecting_releases_the_site_and_counts_no_hours(client):
    claim_id = submitted(client)
    rejected = client.post(
        f"/claims/{claim_id}/review",
        json={"verdict": "reject", "note": "The photos are of a car park"},
        headers=bearer("reviewer"),
    ).json()
    assert rejected["state"] == "released"
    assert client.get(f"/claims/site/{SITE}", headers=bearer("anyone")).json() is None
    assert client.get("/hours/mine", headers=bearer("claimer")).json()["verified"] == 0


def test_hours_are_in_half_hours_and_bounded(client):
    claim_id = claim(client)
    for bad in (0, -1, 0.3, limits.HOURS_MAX + 1):
        assert client.put(f"/claims/{claim_id}/hours", json={"hours": bad}, headers=bearer("claimer")).status_code == 422


def test_deleting_an_account_releases_the_claims_it_was_working_on_and_its_hours(client):
    claim_id = claim(client)
    client.put(f"/claims/{claim_id}/hours", json={"hours": 2}, headers=bearer("claimer"))
    assert client.delete("/me", headers=bearer("claimer")).status_code == 204
    detail = client.get(f"/claims/{claim_id}", headers=bearer("anyone")).json()
    assert detail["state"] == "released" and detail["claimer"] is None
    assert [m["hours"] for m in detail["crew"]] == [None]
