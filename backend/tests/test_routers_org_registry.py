"""Tests for an organization's registry, its sign-off and its coverage report (#1540).

The one that matters most is at the top and is a statement about what these
endpoints do NOT do: **signing off publishes nothing.** Everything else here
is ordinary CRUD with a gate on it; that one is SOURCE_REGISTRY.md's rule
surviving self-service, which is the whole reason an outside organization can
safely be given a seat.
"""

import uuid

from app.models.club import OrgState
from tests.factories import make_admin, make_assignment, make_org, make_profile, make_section
from tests.tokens import auth_headers


def _org_with_admin(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    return org, admin


def test_signing_off_says_in_words_that_it_published_nothing(client, db_session):
    """An organization that thinks it has published and then cannot find its
    trails on a phone will ask us why. The answer belongs where they looked."""
    _, admin = _org_with_admin(db_session)

    response = client.post("/clubs/ramapo-trail-conference/registry/signoff", headers=auth_headers(admin.id))

    assert response.status_code == 202
    detail = response.json()["detail"]
    assert "pull request" in detail
    assert "Approved is not published" in detail


def test_sign_off_takes_three_codeowners(client, db_session):
    _, admin = _org_with_admin(db_session)

    body = client.post("/clubs/ramapo-trail-conference/registry/signoff", headers=auth_headers(admin.id)).json()

    assert body["approvals_required"] == 3


def test_a_non_codeowner_admin_cannot_sign_off(client, db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin, is_codeowner=False)

    response = client.post("/clubs/ramapo-trail-conference/registry/signoff", headers=auth_headers(admin.id))

    assert response.status_code == 403


def test_the_three_tiers_come_back_nested(client, db_session):
    _, admin = _org_with_admin(db_session)
    headers = auth_headers(admin.id)
    park = client.post(
        "/clubs/ramapo-trail-conference/registry/parks",
        json={"name": "Harriman State Park", "kind": "park"},
        headers=headers,
    ).json()
    trail = client.post(
        f"/clubs/ramapo-trail-conference/registry/parks/{park['id']}/trails",
        json={"name": "Pine Meadow Trail", "blaze_value_raw": "Red on white"},
        headers=headers,
    ).json()
    client.post(
        f"/clubs/ramapo-trail-conference/registry/trails/{trail['id']}/sections",
        json={"name": "Pine Meadow North", "start_anchor": "MM 11.0", "end_anchor": "MM 14.3"},
        headers=headers,
    )

    registry = client.get("/clubs/ramapo-trail-conference/registry").json()

    assert registry[0]["name"] == "Harriman State Park"
    assert registry[0]["trails"][0]["blaze_value_raw"] == "Red on white"
    assert registry[0]["trails"][0]["sections"][0]["name"] == "Pine Meadow North"


def test_a_trail_with_no_name_and_no_blaze_is_accepted(client, db_session):
    """A route on a map is a real thing organizations publish. Requiring a name
    here would collect a fake one."""
    _, admin = _org_with_admin(db_session)
    headers = auth_headers(admin.id)
    park = client.post(
        "/clubs/ramapo-trail-conference/registry/parks",
        json={"name": "Ramapo Mountain State Forest"},
        headers=headers,
    ).json()

    response = client.post(
        f"/clubs/ramapo-trail-conference/registry/parks/{park['id']}/trails",
        json={},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["name"] is None


def test_the_organizations_own_blaze_string_is_kept_exactly(client, db_session):
    """`blaze_value_raw` is theirs; `blaze_mapped` is ours. Keeping the raw
    string is what lets a wrong mapping be corrected without going back to the
    source."""
    _, admin = _org_with_admin(db_session)
    headers = auth_headers(admin.id)
    park = client.post("/clubs/ramapo-trail-conference/registry/parks", json={"name": "Harriman"}, headers=headers).json()

    trail = client.post(
        f"/clubs/ramapo-trail-conference/registry/parks/{park['id']}/trails",
        json={"name": "R-D", "blaze_value_raw": "R/W dot", "blaze_mapped": "blaze-white"},
        headers=headers,
    ).json()

    assert trail["blaze_value_raw"] == "R/W dot"
    assert trail["blaze_mapped"] == "blaze-white"


def test_a_stranger_cannot_add_to_somebody_elses_registry(client, db_session):
    make_org(db_session, state=OrgState.claimed)

    response = client.post(
        "/clubs/ramapo-trail-conference/registry/parks",
        json={"name": "Harriman"},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 403


def test_a_pdf_is_refused_as_a_source_and_says_why(client, db_session):
    """Not a technical refusal: accepting a snapshot while implying a feed is
    how a registry quietly ages into fiction."""
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/gis-source",
        json={"url": "https://ramapotrails.org/trails.pdf", "kind": "geojson"},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422
    assert "read again tomorrow" in str(response.json())


def test_a_spreadsheet_is_refused_too(client, db_session):
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/gis-source",
        json={"url": "https://ramapotrails.org/sections.xlsx", "kind": "geojson"},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_a_csv_in_a_query_string_does_not_refuse_a_real_endpoint(client, db_session):
    """An ArcGIS endpoint can legitimately carry `f=csv` as a format parameter
    while being perfectly re-readable. Only the path decides."""
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/gis-source",
        json={"url": "https://services.arcgis.com/x/FeatureServer/0/query?f=csv", "kind": "arcgis"},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 202


def test_registering_a_source_promises_a_probe_rather_than_pretending_one_ran(client, db_session):
    _, admin = _org_with_admin(db_session)

    body = client.post(
        "/clubs/ramapo-trail-conference/gis-source",
        json={"url": "https://services.arcgis.com/x/FeatureServer/0", "kind": "arcgis"},
        headers=auth_headers(admin.id),
    ).json()

    assert "We will read" in body["detail"]
    assert "until your codeowners approve" in body["detail"]


def test_an_unpublished_registry_diff_is_admins_only(client, db_session):
    make_org(db_session, state=OrgState.claimed)

    response = client.get("/clubs/ramapo-trail-conference/registry/diff", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 403


def test_a_section_with_no_live_role_is_a_coverage_gap(client, db_session):
    org, admin = _org_with_admin(db_session)
    make_section(db_session, org, name="Pine Meadow North", region="Harriman")

    body = client.get("/clubs/ramapo-trail-conference/coverage", headers=auth_headers(admin.id)).json()

    assert body["sections_total"] == 1
    assert [gap["section_name"] for gap in body["gaps"]] == ["Pine Meadow North"]


def test_a_section_somebody_currently_holds_is_not_a_gap(client, db_session):
    org, admin = _org_with_admin(db_session)
    section = make_section(db_session, org)
    make_assignment(db_session, org, make_profile(db_session), section=section)

    body = client.get("/clubs/ramapo-trail-conference/coverage", headers=auth_headers(admin.id)).json()

    assert body["gaps"] == []


def test_a_section_whose_assignment_was_closed_becomes_a_gap_again(client, db_session):
    """`effective_to is None` is the whole definition of current, which is what
    makes coverage correct after a hand-off rather than after a tidy-up."""
    import datetime

    org, admin = _org_with_admin(db_session)
    section = make_section(db_session, org)
    make_assignment(
        db_session,
        org,
        make_profile(db_session),
        section=section,
        effective_to=datetime.date.today(),
    )

    body = client.get("/clubs/ramapo-trail-conference/coverage", headers=auth_headers(admin.id)).json()

    assert len(body["gaps"]) == 1


def test_coverage_can_be_read_one_region_at_a_time(client, db_session):
    org, admin = _org_with_admin(db_session)
    make_section(db_session, org, name="Harriman section", region="Harriman")
    make_section(db_session, org, name="Catskills section", region="Catskills")

    body = client.get("/clubs/ramapo-trail-conference/coverage?region=Catskills", headers=auth_headers(admin.id)).json()

    assert [gap["section_name"] for gap in body["gaps"]] == ["Catskills section"]


def test_no_hiker_is_told_which_miles_nobody_looks_after(client, db_session):
    """A gap is flagged, not escalated - and it is never a public signal."""
    org = make_org(db_session, state=OrgState.claimed)
    make_section(db_session, org)

    response = client.get("/clubs/ramapo-trail-conference/coverage", headers=auth_headers(str(uuid.uuid4())))

    assert response.status_code == 403
