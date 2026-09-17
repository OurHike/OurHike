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

from app.models.club import OrgState
from tests.factories import (
    make_admin,
    make_assignment,
    make_org,
    make_profile,
    make_role,
    make_section,
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

    return {"org": org, "people": people, "section": section, "role": under}


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
