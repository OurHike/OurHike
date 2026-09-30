"""Every org endpoint against every kind of person, in one table.

WHY A MATRIX AND NOT MORE INDIVIDUAL TESTS. The per-router files each check
the case that router is about, which catches a wrong guard on one endpoint and
cannot catch the shape of mistake this file exists for: a guard that is right
on nine endpoints and absent on the tenth, or a permission that quietly widens
because `can_manage_volunteers` grew a third disjunct. Written as a table, a
missing row is visible; written as prose, it is not.

THE FIVE PEOPLE, and what makes each one different:

  admin        an approved seat. Everything: the registry, the org's own
               details, the roster, the budget.
  codeowner    an admin who also signs the registry. Only sign-off tells the
               two apart, which is why it is the only row where they differ.
  supervisor   holds a role another live role reports to. Runs crews and reads
               the roster; does not touch the registry and cannot spend the
               assist budget. Derived from the reporting line rather than
               stored - `core/org_access.py` says why.
  maintainer   a live assignment and nothing above them. A volunteer here,
               with no management of anybody.
  outsider     signed in, with an account, and no seat at THIS organization.
               The case a test suite is likeliest to skip and an attacker is
               likeliest to be.
  signed out   no token at all.

WHAT 401 AND 403 MEAN HERE, kept apart on purpose. 401 is "we do not know who
you are"; 403 is "we do and you may not". An endpoint answering 403 to a
signed-out caller would be telling them the resource exists, and one answering
401 to a signed-in one would send them to sign in again to no effect.
"""

from __future__ import annotations

import pytest

from app.core.console_tokens import hash_secret, new_key_pair
from app.models.club import OrgState
from app.models.console_key import ConsoleKey
from app.models.org_registry import OrgPark, OrgSection, OrgTrail
from app.models.org_role import OrgRole
from app.models.work_project import WorkProjectSignup
from tests.factories import (
    make_admin,
    make_assignment,
    make_org,
    make_profile,
    make_role,
    make_section,
    make_workday,
)
from tests.tokens import auth_headers

ADMIN = "admin"
CODEOWNER = "codeowner"
SUPERVISOR = "supervisor"
MAINTAINER = "maintainer"
OUTSIDER = "outsider"
SIGNED_OUT = "signed out"

EVERYBODY = (ADMIN, CODEOWNER, SUPERVISOR, MAINTAINER, OUTSIDER, SIGNED_OUT)


@pytest.fixture
def org_world(db_session):
    """One organization with one of each kind of person at it.

    The supervisor is built from the reporting line rather than a flag,
    because that is the only way to get one: a chair role, a maintainer role
    that reports to it, and a live assignment on each.
    """
    org = make_org(db_session, state=OrgState.claimed)
    section = make_section(db_session, org)

    chair = make_role(db_session, org, name="Trails chair")
    under = make_role(db_session, org, name="Maintainer", reports_to_role_id=chair.id)

    people = {
        ADMIN: make_profile(db_session),
        CODEOWNER: make_profile(db_session),
        SUPERVISOR: make_profile(db_session),
        MAINTAINER: make_profile(db_session),
        OUTSIDER: make_profile(db_session),
    }
    make_admin(db_session, org, people[ADMIN], is_codeowner=False)
    make_admin(db_session, org, people[CODEOWNER], is_codeowner=True)
    make_assignment(db_session, org, people[SUPERVISOR], role=chair, section=section)
    make_assignment(db_session, org, people[MAINTAINER], role=under, section=section)
    db_session.commit()

    trail = db_session.get(OrgTrail, section.trail_id)
    return {
        "org": org,
        "people": people,
        "section": section,
        "role": under,
        "trail_id": trail.id,
        "park_id": trail.park_id,
    }


def _headers(world, who):
    if who == SIGNED_OUT:
        return {}
    return auth_headers(world["people"][who].id)


def _call(client, world, who, method, path, body=None):
    url = path.replace("{slug}", world["org"].slug)
    kwargs = {"headers": _headers(world, who)}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(url, **kwargs)


def _expected(allowed, who):
    """The status a person not in `allowed` should get.

    Signed out is 401 and everybody else is 403, everywhere. Keeping the two
    apart is the point: 401 says "we do not know who you are" and 403 says
    "we do".
    """
    if who in allowed:
        return None
    return 401 if who == SIGNED_OUT else 403


# ------------------------------------------------------------------ #
# Reads
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("who", EVERYBODY)
def test_anybody_at_all_can_read_an_organizations_public_face(client, org_world, who):
    """The org record, its registry and its coverage are what a hiker sees on
    the map. Putting a gate on them would gate the map."""
    for path in ("/clubs/{slug}", "/clubs/{slug}/registry"):
        response = _call(client, org_world, who, "get", path)
        assert response.status_code == 200, f"{who} could not read {path}"


@pytest.mark.parametrize("who", EVERYBODY)
def test_the_roster_reaches_admins_and_supervisors_and_nobody_else(client, org_world, who):
    """Names, emails and assignments - everything rule 4 keeps unpublished.

    A maintainer is deliberately outside this. They are a volunteer here, and
    a volunteer having every colleague's address because they hold a section
    is not a permission anybody asked for.
    """
    response = _call(client, org_world, who, "get", "/clubs/{slug}/roster")
    expected = _expected({ADMIN, CODEOWNER, SUPERVISOR}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_the_export_reaches_admins_only(client, org_world, who):
    """A supervisor reads the roster SCREEN and cannot download the FILE.

    One is a supervisor looking somebody up; the other is a copy of every
    name and address leaving the building.
    """
    response = _call(client, org_world, who, "get", "/clubs/{slug}/export")
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_the_console_keys_reach_admins_only(client, org_world, who):
    """A key mints tokens that render a roster on a third-party site."""
    response = _call(client, org_world, who, "get", "/clubs/{slug}/console-keys")
    expected = _expected({ADMIN, CODEOWNER}, who)

    if expected is None:
        assert response.status_code in (200, 503)
    else:
        assert response.status_code == expected


# ------------------------------------------------------------------ #
# Writes
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("who", EVERYBODY)
def test_the_registry_is_an_admins_to_touch(client, org_world, who):
    """Not a supervisor's. The registry is what reaches a hiker's phone, and
    running crews is a different job from publishing trails."""
    response = _call(
        client,
        org_world,
        who,
        "post",
        "/clubs/{slug}/gis-source",
        {"url": "https://gis.example.org/FeatureServer/0", "kind": "arcgis"},
    )
    expected = _expected({ADMIN, CODEOWNER}, who)

    # 202, exactly. "< 400 or 422" was the first version of this line and it
    # would have passed on almost anything, which makes it a test that cannot
    # fail rather than one that has not.
    assert response.status_code == (202 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_signing_off_the_registry_is_a_codeowners_act_alone(client, org_world, who):
    """The one row where an admin and a codeowner differ.

    An admin who is not a codeowner runs the organization and does not sign
    for what its trails say - that is the whole of what `is_codeowner` buys.
    """
    response = _call(client, org_world, who, "post", "/clubs/{slug}/registry/signoff")
    expected = _expected({CODEOWNER}, who)

    assert response.status_code == (202 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_the_organizations_own_details_are_an_admins_to_change(client, org_world, who):
    response = _call(client, org_world, who, "patch", "/clubs/{slug}", {"region": "Harriman"})
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_defining_a_role_is_an_admins_act(client, org_world, who):
    """A role is a claim about who is responsible for a stretch of trail.

    A supervisor proposes people for roles and does not invent the roles -
    otherwise a supervisor could define one that reports to nobody and
    escape their own reporting line.
    """
    response = _call(
        client,
        org_world,
        who,
        "post",
        "/clubs/{slug}/roles",
        {"name": "Corridor monitor", "category": "trail_maintenance"},
    )
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (201 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_running_crews_reaches_supervisors_too(client, org_world, who):
    """The one permission a supervisor has that a maintainer does not.

    Workdays, signup replies, hours confirmation and roster loading are a job
    supervisors and chairs already do off-app.
    """
    response = _call(
        client,
        org_world,
        who,
        "post",
        "/clubs/{slug}/workdays",
        {
            "title": "Blowdown sweep",
            "starts_on": "2026-10-03",
            "ends_on": "2026-10-03",
            "signup_mode": "in_app",
        },
    )
    expected = _expected({ADMIN, CODEOWNER, SUPERVISOR}, who)

    if expected is None:
        assert response.status_code in (200, 201)
    else:
        assert response.status_code == expected


@pytest.mark.parametrize("who", EVERYBODY)
def test_inviting_a_volunteer_reaches_supervisors_too(client, org_world, who):
    response = _call(
        client,
        org_world,
        who,
        "post",
        "/clubs/{slug}/invites",
        {"email": "newcomer@example.org"},
    )
    expected = _expected({ADMIN, CODEOWNER, SUPERVISOR}, who)

    if expected is None:
        assert response.status_code in (200, 201)
    else:
        assert response.status_code == expected


@pytest.mark.parametrize("who", EVERYBODY)
def test_confirming_an_assignment_is_an_admins_act_not_a_supervisors(client, org_world, who):
    """Supervisors propose, admins confirm.

    The replacement guardrail for the no-HTTP-writes rule
    (features/ORG_ONBOARDING.md): a wrong section assignment sends a hiker's
    report to the wrong person for as long as nobody notices, so the person
    who proposed it is not the person who makes it live.
    """
    response = _call(client, org_world, who, "post", "/clubs/{slug}/assignments/does-not-exist/confirm")
    expected = _expected({ADMIN, CODEOWNER}, who)

    # A 404 for the made-up assignment id is the PASS here: it means the
    # guard let them through to look for it. Anybody refused never got that
    # far, which is exactly the distinction being asserted.
    assert response.status_code == (404 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_deleting_the_organization_is_an_admins_act(client, org_world, who):
    response = _call(client, org_world, who, "delete", "/clubs/{slug}")
    expected = _expected({ADMIN, CODEOWNER}, who)

    if expected is None:
        assert response.status_code in (200, 202, 204)
    else:
        assert response.status_code == expected


@pytest.mark.parametrize("who", EVERYBODY)
def test_spending_the_assist_budget_is_an_admins_act(client, org_world, who, monkeypatch):
    """A supervisor who could spend it could exhaust it before an admin
    reached the screen. 503 for an admin means the panels are off, which is
    the default - and is still the guard having let them through."""
    response = _call(
        client,
        org_world,
        who,
        "post",
        "/clubs/{slug}/assist",
        {"panel": "registry", "question": "what is on our server?"},
    )
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (503 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_deciding_whether_a_model_may_read_the_registry_is_an_admins_act(client, org_world, who):
    """The same gate as spending the budget, for the decision behind it.

    A supervisor runs crews. Whether this organization's section names, trail
    names and mileages may be read by a third party is the organization's
    decision, and it sits with the people whose seat says they speak for it.
    """
    response = _call(
        client,
        org_world,
        who,
        "put",
        "/clubs/{slug}/assist-consent",
        {"opted_in": True},
    )
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_who_agreed_to_the_assistant_is_not_a_public_reading(client, org_world, who):
    """The boolean is public on the org; the name and the date are not.

    `GET /clubs/{slug}` carries `assist_opted_in` to anybody, because whether
    an organization uses the panels is a fact about the organization. Which of
    its admins clicked the button on which afternoon is a fact about a person.
    """
    response = _call(client, org_world, who, "get", "/clubs/{slug}/assist-consent")
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (200 if expected is None else expected)


# ------------------------------------------------------------------ #
# The rows #1643 found missing
#
# The v1.3.2 release review's test-gap pass (#1643 - The org console's
# permission matrix skips ten endpoints, and the position mark and outbox
# drain have no end-to-end test) read the org writes in `app/routers/`
# against this file and found these with no row. Each is written in the same
# shape as the rows above: the exact success status for the people allowed,
# and `_expected` for everybody else.
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("who", EVERYBODY)
def test_inviting_another_admin_is_an_admins_act(client, org_world, who):
    """A seat is the whole of the organization's authority, so offering one is too."""
    response = _call(client, org_world, who, "post", "/clubs/{slug}/admins", {"email": "secretary@example.org"})
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (201 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_editing_a_role_is_an_admins_act(client, db_session, org_world, who):
    """Editing a role can move its reporting line, so it has `POST /roles`'s
    gate for `POST /roles`'s reason."""
    role = make_role(db_session, org_world["org"], name="Corridor monitor")
    response = _call(client, org_world, who, "patch", f"/clubs/{{slug}}/roles/{role.id}", {"name": "Boundary monitor"})
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_retiring_a_role_is_an_admins_act(client, db_session, org_world, who):
    role = make_role(db_session, org_world["org"], name="Corridor monitor")
    response = _call(client, org_world, who, "delete", f"/clubs/{{slug}}/roles/{role.id}")
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_adding_a_park_to_the_registry_is_an_admins_act(client, org_world, who):
    """Every registry tier reaches a hiker's phone, the same as the
    `gis-source` row above - so each tier gets its own row rather than being
    assumed to share that one's guard."""
    response = _call(client, org_world, who, "post", "/clubs/{slug}/registry/parks", {"name": "Harriman State Park"})
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (201 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_adding_a_trail_to_the_registry_is_an_admins_act(client, org_world, who):
    path = f"/clubs/{{slug}}/registry/parks/{org_world['park_id']}/trails"
    response = _call(client, org_world, who, "post", path, {"name": "Suffern-Bear Mountain"})
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (201 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_adding_a_section_to_the_registry_is_an_admins_act(client, org_world, who):
    path = f"/clubs/{{slug}}/registry/trails/{org_world['trail_id']}/sections"
    body = {"name": "Pine Meadow South", "start_mile": 14.3, "end_mile": 16.0}
    response = _call(client, org_world, who, "post", path, body)
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (201 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_putting_somebody_on_a_stretch_reaches_supervisors_too(client, org_world, who):
    """Supervisors propose: the write is let through and lands unconfirmed,
    and `test_confirming_an_assignment_is_an_admins_act_not_a_supervisors` is
    the other half. A maintainer proposes nobody."""
    body = {
        "person_id": org_world["people"][MAINTAINER].id,
        "section_id": org_world["section"].id,
        "start_mile": 11.5,
        "end_mile": 12.0,
    }
    response = _call(client, org_world, who, "post", "/clubs/{slug}/assignments", body)
    expected = _expected({ADMIN, CODEOWNER, SUPERVISOR}, who)

    assert response.status_code == (201 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_loading_a_roster_reaches_supervisors_too(client, org_world, who):
    """Roster loading is one of the crew jobs `test_running_crews_reaches_supervisors_too`
    names. A maintainer allowed to load one could deactivate every colleague."""
    body = {"source": "uploaded roster.csv", "entries": [{"email": "ana@ramapotrails.org"}]}
    response = _call(client, org_world, who, "post", "/clubs/{slug}/roster/sync", body)
    expected = _expected({ADMIN, CODEOWNER, SUPERVISOR}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_revoking_a_console_key_is_an_admins_act(client, db_session, org_world, who):
    """Listing keys is admin-only (the row above); revoking one is the write
    that switches off an organization's own embedded roster page."""
    public_key, secret = new_key_pair()
    key = ConsoleKey(club_id=org_world["org"].id, public_key=public_key, secret_hash=hash_secret(secret))
    db_session.add(key)
    db_session.commit()

    response = _call(client, org_world, who, "delete", f"/clubs/{{slug}}/console-keys/{key.id}")
    expected = _expected({ADMIN, CODEOWNER}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_calling_off_a_workday_reaches_supervisors_too(client, db_session, org_world, who):
    """`/workdays/{id}/cancel` carries no slug, so its guard is resolved from
    the workday's own organization inside the handler, not by the
    `require_*` dependencies every slug route above goes through."""
    project = make_workday(db_session, org_world["org"])

    response = _call(client, org_world, who, "post", f"/workdays/{project.id}/cancel")
    expected = _expected({ADMIN, CODEOWNER, SUPERVISOR}, who)

    assert response.status_code == (200 if expected is None else expected)


@pytest.mark.parametrize("who", EVERYBODY)
def test_recording_attendance_reaches_supervisors_too(client, db_session, org_world, who):
    """Attendance pre-fills an hours claim an organization reports onward, so a
    volunteer recording their own is the case this row refuses."""
    project = make_workday(db_session, org_world["org"])
    signup = WorkProjectSignup(work_project_id=project.id, person_id=org_world["people"][MAINTAINER].id)
    db_session.add(signup)
    db_session.commit()

    path = f"/workdays/{project.id}/signups/{signup.id}/attendance"
    response = _call(client, org_world, who, "post", path, {"attended": 1})
    expected = _expected({ADMIN, CODEOWNER, SUPERVISOR}, who)

    assert response.status_code == (200 if expected is None else expected)


def test_ids_from_another_organization_are_404_here(client, db_session, org_world):
    """An admin of B, naming A's role, key, park or trail under B's own slug.

    B's admin passes B's gate honestly - they ARE an admin there - so the
    only thing standing between them and A's rows is each handler filtering
    the id by `club_id`. 404 rather than 403, because a 403 would confirm the
    id exists somewhere. A's rows are read back afterwards: a handler that
    answered 404 after writing would pass the status check alone.
    """
    a = org_world["org"]
    role = make_role(db_session, a, name="Corridor monitor")
    public_key, secret = new_key_pair()
    key = ConsoleKey(club_id=a.id, public_key=public_key, secret_hash=hash_secret(secret))
    db_session.add(key)
    db_session.commit()
    role_id, key_id = role.id, key.id

    b = make_org(db_session, slug="another-conference", state=OrgState.claimed)
    b_admin = make_profile(db_session)
    make_admin(db_session, b, b_admin, is_codeowner=True)
    db_session.commit()

    for method, path, body in (
        ("patch", f"/clubs/{b.slug}/roles/{role_id}", {"name": "Taken over"}),
        ("delete", f"/clubs/{b.slug}/roles/{role_id}", None),
        ("delete", f"/clubs/{b.slug}/console-keys/{key_id}", None),
        ("post", f"/clubs/{b.slug}/registry/parks/{org_world['park_id']}/trails", {"name": "Planted"}),
        ("post", f"/clubs/{b.slug}/registry/trails/{org_world['trail_id']}/sections", {"name": "Planted"}),
    ):
        kwargs = {"headers": auth_headers(b_admin.id)}
        if body is not None:
            kwargs["json"] = body
        assert getattr(client, method)(path, **kwargs).status_code == 404, f"{method} {path}"

    db_session.expire_all()
    role_after = db_session.get(OrgRole, role_id)
    assert role_after is not None and role_after.name == "Corridor monitor"
    assert role_after.retired_at is None
    assert db_session.get(ConsoleKey, key_id).revoked_at is None
    assert db_session.query(OrgTrail).filter(OrgTrail.park_id == org_world["park_id"]).count() == 1
    assert db_session.query(OrgSection).filter(OrgSection.trail_id == org_world["trail_id"]).count() == 1
    assert db_session.query(OrgPark).filter(OrgPark.club_id == b.id).count() == 0


# ------------------------------------------------------------------ #
# The outsider, on their own
# ------------------------------------------------------------------ #


def test_a_seat_at_one_organization_is_not_a_seat_at_another(client, db_session, org_world):
    """The mistake a permission model makes once and cannot make quietly.

    Somebody who is a codeowner at their own organization has no standing at
    anybody else's, and the check has to be per-organization rather than per
    person.
    """
    theirs = make_org(db_session, slug="another-conference", state=OrgState.claimed)
    stranger = make_profile(db_session)
    make_admin(db_session, theirs, stranger, is_codeowner=True)
    db_session.commit()

    for method, path, body in (
        ("get", "/clubs/{slug}/roster", None),
        ("get", "/clubs/{slug}/export", None),
        ("patch", "/clubs/{slug}", {"region": "nope"}),
        ("delete", "/clubs/{slug}", None),
    ):
        url = path.replace("{slug}", org_world["org"].slug)
        kwargs = {"headers": auth_headers(stranger.id)}
        if body is not None:
            kwargs["json"] = body
        assert getattr(client, method)(url, **kwargs).status_code == 403, f"{method} {path}"


def test_an_invited_admin_who_has_not_approved_is_not_an_admin_yet(client, db_session, org_world):
    """`approved_at` is the gate, not the invitation.

    An invited secretary who has not answered cannot publish a registry -
    otherwise naming somebody as an admin would grant the access before they
    had agreed to hold it.
    """
    invited = make_profile(db_session)
    make_admin(db_session, org_world["org"], invited, approved=False)
    db_session.commit()

    response = client.get(f"/clubs/{org_world['org'].slug}/export", headers=auth_headers(invited.id))

    assert response.status_code == 403


def test_the_access_endpoint_tells_each_person_the_truth_about_themselves(client, org_world):
    """The rail draws from this, so a wrong answer here is a screen offering
    somebody a door that is locked."""
    expected = {
        ADMIN: {"is_admin": True, "is_codeowner": False, "can_touch_registry": True},
        CODEOWNER: {"is_admin": True, "is_codeowner": True, "can_touch_registry": True},
        SUPERVISOR: {"is_admin": False, "is_supervisor": True, "can_read_roster": True},
        MAINTAINER: {"is_admin": False, "is_supervisor": False, "is_volunteer": True},
        OUTSIDER: {"is_admin": False, "is_supervisor": False, "is_volunteer": False},
    }

    for who, wanted in expected.items():
        body = _call(client, org_world, who, "get", "/clubs/{slug}/access").json()
        for key, value in wanted.items():
            assert body[key] is value, f"{who}: {key} was {body[key]}, wanted {value}"


def test_a_maintainer_can_read_the_roster_of_nothing_and_still_walk_their_miles(client, org_world):
    """The point of separating `is_volunteer` from the management flags.

    A maintainer is refused the roster and is NOT refused the organization -
    they hold a section here, and a model that answered 403 to everything
    would lock a volunteer out of their own trails.
    """
    assert _call(client, org_world, MAINTAINER, "get", "/clubs/{slug}/roster").status_code == 403
    assert _call(client, org_world, MAINTAINER, "get", "/clubs/{slug}").status_code == 200

    body = _call(client, org_world, MAINTAINER, "get", "/clubs/{slug}/access").json()
    assert body["is_volunteer"] is True
    assert body["can_manage_volunteers"] is False
