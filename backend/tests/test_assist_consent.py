"""Whether the organization agreed that a model may read its data.

The panels send section names, trail names, mileages and the coverage gap
list to a third party at api.anthropic.com. The screen saying so is true and
is not consent, which is what this file is about: a per-organization opt-in,
off for every organization until one of its own admins turns it on.

**THE GATE IS IN `app/core/assist.py` AND NOT IN THE ROUTER**, so these tests
go through the HTTP surface and also assert the thing that matters more -
that `httpx.post` was never reached. A 409 that still made the call would
pass a status assertion and fail the organization.

**NOTHING IS ASKED BEFORE THE ORGANIZATION EXISTS.** Registration collects no
consent: there is nobody at an organization that does not exist yet to give
it, and a checkbox on a sign-up form is the weakest place to collect a
decision about somebody else's data. The public nominate panel is outside the
gate for the same reason - it runs before any org record exists, sends a
website address a hiker typed, and carries nothing of any organization's.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.config import settings
from app.core import assist as assist_core
from app.core.time import utc_now
from app.models.club import Club, OrgState
from tests.factories import make_admin, make_assignment, make_org, make_profile, make_role
from tests.nominating import answers, reads, solved, switch_on
from tests.tokens import auth_headers


@pytest.fixture
def assist_on(monkeypatch):
    """The deployment switch on, so consent is the only thing left in the way."""
    monkeypatch.setattr(settings, "assist_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-not-a-real-key")
    monkeypatch.setattr(settings, "assist_model", "claude-sonnet-5")
    return settings


@pytest.fixture
def answered(monkeypatch):
    """A canned reply, for the tests about a call that should go through."""

    def fake_post(url, *, timeout, headers, json):
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "content": [{"type": "text", "text": "Read 312 sections."}],
                "usage": {"input_tokens": 120, "output_tokens": 40},
            },
        )

    monkeypatch.setattr(assist_core.httpx, "post", fake_post)


@pytest.fixture
def nothing_leaves(monkeypatch):
    """Fails the test if anything reaches the API at all.

    The assertion this file is really making. A refusal that answered 409
    after the request had already gone out would be a screen apologising for
    something that had already happened.
    """

    def refuse_to_be_called(*args, **kwargs):
        raise AssertionError("a request reached api.anthropic.com for an org that had not agreed")

    monkeypatch.setattr(assist_core.httpx, "post", refuse_to_be_called)


def _org_with_admin(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    person = make_profile(db_session)
    make_admin(db_session, org, person)
    return org, person


def _ask(client, org, person):
    return client.post(
        f"/clubs/{org.slug}/assist",
        json={"panel": "registry", "question": "what is on our server?"},
        headers=auth_headers(person.id),
    )


def _set_consent(client, org, person, opted_in):
    return client.put(
        f"/clubs/{org.slug}/assist-consent",
        json={"opted_in": opted_in},
        headers=auth_headers(person.id),
    )


def test_an_organization_starts_with_the_assistant_off(client, db_session):
    """Nobody has been asked, so nobody has agreed."""
    org, person = _org_with_admin(db_session)

    body = client.get(f"/clubs/{org.slug}").json()

    assert body["assist_opted_in"] is False


def test_registering_does_not_collect_consent_and_cannot_set_it(client, db_session):
    """There is nobody at an organization that does not exist yet to agree.

    A field smuggled into the registration body is ignored rather than
    honoured - the switch is a deliberate act in Settings afterwards, by an
    admin whose seat has been approved, not a line in the form that created
    the organization.
    """
    founder = str(uuid.uuid4())

    created = client.post(
        "/clubs",
        json={
            "name": "Ramapo Trail Conference",
            "slug": "ramapo-trail-conference",
            "domain": "ramapotrails.org",
            "assist_opted_in": True,
            "assist_opted_in_at": "2020-01-01T00:00:00Z",
        },
        headers=auth_headers(founder, email="chair@ramapotrails.org"),
    )

    assert created.status_code in (200, 201)
    assert created.json()["assist_opted_in"] is False
    row = db_session.query(Club).filter(Club.slug == "ramapo-trail-conference").one()
    assert row.assist_opted_in_at is None


def test_the_settings_patch_cannot_switch_the_assistant_on(client, db_session, assist_on, nothing_leaves):
    """The other door into the same row, and it stays shut.

    `PATCH /clubs/{slug}` writes its fields straight onto the row, so a
    consent field accepted there would be consent with no date and nobody's
    name against it. `OrgSettingsUpdate` does not declare one, and pydantic
    drops what it does not declare - asserted rather than assumed, because
    "extra fields are ignored" is a default somebody could change.
    """
    org, person = _org_with_admin(db_session)

    updated = client.patch(
        f"/clubs/{org.slug}",
        json={"region": "Hudson Valley", "assist_opted_in_at": "2020-01-01T00:00:00Z"},
        headers=auth_headers(person.id),
    )

    assert updated.status_code == 200
    assert updated.json()["region"] == "Hudson Valley"
    assert updated.json()["assist_opted_in"] is False
    assert _ask(client, org, person).status_code == 409


def test_an_organization_that_has_not_agreed_is_refused_before_anything_is_sent(client, db_session, assist_on, nothing_leaves):
    """The whole file in one test. 409, and `nothing_leaves` proves the rest."""
    org, person = _org_with_admin(db_session)

    response = _ask(client, org, person)

    assert response.status_code == 409
    assert "has not turned the assistant on" in response.text


def test_the_refusal_is_409_rather_than_403_so_a_screen_can_tell_them_apart(client, db_session, assist_on, nothing_leaves):
    """A 403 here already means "you are not an admin".

    A supervisor told "your organization has not agreed to this" would be a
    screen reporting somebody else's decision in place of their own missing
    permission.
    """
    org, admin = _org_with_admin(db_session)
    role = make_role(db_session, org, name="Trails chair")
    make_role(db_session, org, name="Maintainer", reports_to_role_id=role.id)
    supervisor = make_profile(db_session)
    make_assignment(db_session, org, supervisor, role=role)

    assert _ask(client, org, admin).status_code == 409
    assert _ask(client, org, supervisor).status_code == 403


def test_an_admin_turning_it_on_lets_the_next_question_through(client, db_session, assist_on, answered):
    org, person = _org_with_admin(db_session)

    assert _set_consent(client, org, person, True).status_code == 200

    assert _ask(client, org, person).status_code == 200


def test_who_agreed_and_when_is_recorded_rather_than_just_that_somebody_did(client, db_session, assist_on):
    """A boolean would answer "is it on" and nothing else.

    An organization asking six months later who agreed to this needs a name
    and a date, and the row is the only place either could come from.
    """
    org, person = _org_with_admin(db_session)

    body = _set_consent(client, org, person, True).json()

    assert body["opted_in"] is True
    assert body["opted_in_by"] == person.id
    assert body["opted_in_at"] is not None
    assert body["opted_out_at"] is None


def test_turning_it_off_refuses_the_next_question_and_keeps_the_record(client, db_session, assist_on, nothing_leaves):
    """Withdrawing works, and does not erase that it was ever on.

    "Was our data ever sent, and between which dates" is a question an
    organization is entitled to ask, and an opt-out that wiped the opt-in
    would leave nothing to answer it with.
    """
    org, person = _org_with_admin(db_session)
    _set_consent(client, org, person, True)

    off = _set_consent(client, org, person, False).json()

    assert off["opted_in"] is False
    assert off["opted_in_at"] is not None
    assert off["opted_out_at"] is not None
    assert _ask(client, org, person).status_code == 409


def test_an_organization_can_change_its_mind_back(client, db_session, assist_on, answered):
    """Off, then on again. The later date is the standing one."""
    org, person = _org_with_admin(db_session)
    _set_consent(client, org, person, True)
    _set_consent(client, org, person, False)

    back_on = _set_consent(client, org, person, True).json()

    assert back_on["opted_in"] is True
    assert back_on["opted_out_at"] is None
    assert _ask(client, org, person).status_code == 200


def test_two_timestamps_to_the_microsecond_read_as_off(client, db_session, assist_on, nothing_leaves):
    """Not a state anybody clicks their way into, so it means a row somebody
    edited or a clock that went backwards.

    Of the two ways to be wrong, sending an organization's registry to a
    third party they did not choose is the one that cannot be taken back.
    """
    org, person = _org_with_admin(db_session)
    same_moment = utc_now()
    org.assist_opted_in_at = same_moment
    org.assist_opted_in_by = person.id
    org.assist_opted_out_at = same_moment
    db_session.commit()

    assert _ask(client, org, person).status_code == 409


def test_one_organizations_consent_does_not_switch_on_anothers(client, db_session, assist_on, nothing_leaves):
    org, person = _org_with_admin(db_session)
    _set_consent(client, org, person, True)
    other = make_org(db_session, slug="another-club", state=OrgState.claimed)
    make_admin(db_session, other, person)

    assert _ask(client, other, person).status_code == 409


def test_a_deployment_with_the_panels_off_says_so_rather_than_blaming_the_org(client, db_session, nothing_leaves):
    """503 before 409, because one of them is fixable by the reader.

    An admin told to go and turn the assistant on, on a deployment where it
    could never work, would do it and get nothing.
    """
    org, person = _org_with_admin(db_session)
    _set_consent(client, org, person, False)

    assert _ask(client, org, person).status_code == 503


def test_consent_is_checked_before_the_budget(client, db_session, assist_on, nothing_leaves):
    """Two refusals, and only one of them is about this organization's day.

    An org that never agreed should not be told it has spent a budget it was
    never able to spend.
    """
    org, person = _org_with_admin(db_session)

    assert _ask(client, org, person).status_code == 409


@pytest.mark.parametrize("opted_in", [True, False])
def test_a_supervisor_cannot_decide_this_for_the_organization(client, db_session, opted_in):
    """Running crews is not the same job as agreeing what leaves the building."""
    org, _ = _org_with_admin(db_session)
    role = make_role(db_session, org, name="Trails chair")
    make_role(db_session, org, name="Maintainer", reports_to_role_id=role.id)
    supervisor = make_profile(db_session)
    make_assignment(db_session, org, supervisor, role=role)

    assert _set_consent(client, org, supervisor, opted_in).status_code == 403


def test_a_volunteer_cannot_decide_it_either(client, db_session):
    org, _ = _org_with_admin(db_session)
    volunteer = make_profile(db_session)
    make_assignment(db_session, org, volunteer)

    assert _set_consent(client, org, volunteer, True).status_code == 403


def test_an_admin_whose_seat_is_not_approved_yet_cannot_decide_it(client, db_session):
    """An invited secretary who has not answered is not an admin."""
    org, _ = _org_with_admin(db_session)
    pending = make_profile(db_session)
    make_admin(db_session, org, pending, approved=False)

    assert _set_consent(client, org, pending, True).status_code == 403


def test_somebody_with_no_seat_here_cannot_decide_it(client, db_session):
    org, _ = _org_with_admin(db_session)
    outsider = make_profile(db_session)

    assert _set_consent(client, org, outsider, True).status_code == 403


def test_a_signed_out_caller_cannot_decide_it(client, db_session):
    """401 rather than 403: one says we do not know who you are."""
    org, _ = _org_with_admin(db_session)

    response = client.put(f"/clubs/{org.slug}/assist-consent", json={"opted_in": True})

    assert response.status_code == 401


def test_reading_where_consent_stands_needs_an_admin_too(client, db_session):
    """The boolean is public on the org; the name and the date are not.

    Which of an organization's admins clicked a button on which afternoon is
    a fact about a person, and a hiker reading the org's page has no use for
    it.
    """
    org, person = _org_with_admin(db_session)
    outsider = make_profile(db_session)

    assert client.get(f"/clubs/{org.slug}/assist-consent", headers=auth_headers(person.id)).status_code == 200
    assert client.get(f"/clubs/{org.slug}/assist-consent", headers=auth_headers(outsider.id)).status_code == 403
    assert "opted_in_by" not in client.get(f"/clubs/{org.slug}").text


def test_the_nominate_panel_runs_before_any_organization_exists(client, db_session, assist_on, monkeypatch):
    """The user-facing half of "nothing is asked before the org is created".

    A hiker nominating their local club is looking at a website that is
    already public, and there is no org record to consent - the organization
    has not been created, which is the point of the form. Asking the hiker to
    agree on the organization's behalf would be a consent worth less than
    none.

    The panel stopped being public on 2026-09-17 and this test grew three
    gates because of it, but the thing it asserts did not change: the consent
    gate in app/core/assist.py is reached with `club=None` and lets the call
    through, because there is nobody to ask.
    """
    switch_on(monkeypatch)
    reads(monkeypatch)
    answers(monkeypatch)
    hiker = make_profile(db_session)

    response = client.post(
        "/assist/nominate",
        json={"website": "https://carolinamountainclub.org", **solved(hiker.id)},
        headers=auth_headers(hiker.id),
    )

    assert response.status_code == 200


def test_an_org_that_said_no_does_not_switch_off_the_nominate_panel(client, db_session, assist_on, monkeypatch):
    """Two different surfaces, two different questions, no shared switch."""
    org, person = _org_with_admin(db_session)
    _set_consent(client, org, person, False)
    switch_on(monkeypatch)
    reads(monkeypatch)
    answers(monkeypatch)
    hiker = make_profile(db_session)

    response = client.post(
        "/assist/nominate",
        json={"website": "https://carolinamountainclub.org", **solved(hiker.id)},
        headers=auth_headers(hiker.id),
    )

    assert response.status_code == 200
