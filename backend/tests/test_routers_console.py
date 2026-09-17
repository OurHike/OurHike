"""Tests for the management-console embed's key exchange (#1542).

**The first test is the most important one in this file**, and it is about
the endpoint doing nothing: `console_embed_enabled` defaults false, so a
deployment that has not deliberately switched this on cannot mint a token at
all. That is the maintainer's build-it-anyway decision and my
security-review reservation, both honoured - the code is real and it is
inert.

The rest walk the six guards. Each has a test named after what it prevents
rather than after the mechanism, because the mechanism is in the model and the
thing worth asserting is the outcome.
"""

import uuid

import pytest

from app.config import settings
from app.core.console_tokens import mint_token, read_token
from app.models.club import OrgState
from app.models.console_key import ConsoleTokenGrant
from app.models.org_role import RoleInvite
from tests.factories import make_admin, make_assignment, make_org, make_profile
from tests.tokens import auth_headers

ORIGIN = "https://ramapotrails.org"


@pytest.fixture()
def console_on(monkeypatch):
    """Switch the embed on for one test.

    A fixture rather than a global, so the default - off - is what every test
    that does not ask sees, which is the same posture the code takes.
    """
    monkeypatch.setattr(settings, "console_embed_enabled", True)
    return True


def _org_with_admin(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    return org, admin


def _make_key(client, admin_id, origins=(ORIGIN,)):
    return client.post(
        "/clubs/ramapo-trail-conference/console-keys",
        json={"label": "members area", "allowed_origins": list(origins)},
        headers=auth_headers(admin_id),
    ).json()


def test_the_session_endpoint_is_inert_until_a_deployment_switches_it_on(client, db_session):
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)

    response = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "maria@ramapotrails.org"},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 503
    assert "security review" in response.json()["detail"]


def test_the_secret_is_returned_once_and_never_by_a_list(client, db_session):
    """Two models rather than one with an optional field: an optional secret is
    a secret that leaks the day somebody reuses the model on a list."""
    _, admin = _org_with_admin(db_session)
    created = _make_key(client, admin.id)

    listed = client.get("/clubs/ramapo-trail-conference/console-keys", headers=auth_headers(admin.id)).json()

    assert created["secret"].startswith("ohs_")
    assert "secret" not in listed[0]


def test_a_new_key_cannot_write(client, db_session):
    """Guard 6 - the one that means a key pasted into a public page by mistake
    cannot change anything."""
    _, admin = _org_with_admin(db_session)

    assert _make_key(client, admin.id)["can_write"] is False


def test_an_organization_can_hold_two_keys_at_once(client, db_session):
    """Guard 4 - rotation is add, swap, delete, with no window where their page
    is broken."""
    _, admin = _org_with_admin(db_session)

    _make_key(client, admin.id)
    _make_key(client, admin.id, origins=["https://staging.ramapotrails.org"])

    listed = client.get("/clubs/ramapo-trail-conference/console-keys", headers=auth_headers(admin.id)).json()
    assert len(listed) == 2


def test_a_wildcard_origin_is_refused(client, db_session):
    """A wildcard here is the allow-list undone."""
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/console-keys",
        json={"allowed_origins": ["https://*.ramapotrails.org"]},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_an_origin_without_a_scheme_is_refused(client, db_session):
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/console-keys",
        json={"allowed_origins": ["ramapotrails.org"]},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_a_key_with_no_origins_is_refused(client, db_session):
    _, admin = _org_with_admin(db_session)

    response = client.post(
        "/clubs/ramapo-trail-conference/console-keys",
        json={"allowed_origins": []},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422


def test_only_an_admin_can_mint_a_key(client, db_session):
    make_org(db_session, state=OrgState.claimed)

    response = client.post(
        "/clubs/ramapo-trail-conference/console-keys",
        json={"allowed_origins": [ORIGIN]},
        headers=auth_headers(str(uuid.uuid4())),
    )

    assert response.status_code == 403


def test_a_real_exchange_mints_a_scoped_token(client, db_session, console_on):
    org, admin = _org_with_admin(db_session)
    volunteer = make_profile(db_session)
    make_assignment(db_session, org, volunteer)
    db_session.add(
        RoleInvite(
            club_id=org.id,
            email="ana@ramapotrails.org",
            claimed_by=volunteer.id,
            claimed_at="2026-09-01",
        )
    )
    db_session.commit()
    key = _make_key(client, admin.id)

    response = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "Ana@Ramapotrails.org"},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["org_slug"] == "ramapo-trail-conference"
    assert body["expires_in"] == 900
    assert read_token(body["token"], origin=ORIGIN) is not None


def test_somebody_not_on_the_roster_gets_a_no_permission_token_rather_than_an_error(client, db_session, console_on):
    """The difference between an organization's members area showing a page
    with nothing on it and showing their own members a stack trace."""
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)

    response = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "stranger@example.org"},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 200
    assert response.json()["permissions"] == []


def test_the_public_key_alone_opens_nothing(client, db_session, console_on):
    """Guard 1. It is in the HTML of somebody's website by design."""
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)

    response = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": "ohs_guessed", "email": "a@b.org"},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 403


def test_a_key_used_from_an_origin_it_was_not_given_is_refused(client, db_session, console_on):
    """Guard 2, and the refusal is deliberately indistinguishable from a wrong
    secret - telling them apart hands somebody an oracle."""
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)

    response = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "a@b.org"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "That key cannot mint a session from this origin"


def test_a_revoked_key_mints_nothing(client, db_session, console_on):
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)
    client.delete(f"/clubs/ramapo-trail-conference/console-keys/{key['id']}", headers=auth_headers(admin.id))

    response = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "a@b.org"},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 403


def test_every_token_request_is_logged_with_its_origin(client, db_session, console_on):
    """Guard 5. "Who has been trying this key, and from where" is the question
    an organization asks the day it leaks."""
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)

    client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "stranger@example.org"},
        headers={"Origin": ORIGIN},
    )

    grant = db_session.query(ConsoleTokenGrant).one()
    assert grant.origin == ORIGIN
    assert grant.resolved is False


def test_the_grant_log_stores_a_hash_rather_than_the_address(client, db_session, console_on):
    """It exists to show a pattern, not to build a second copy of an
    organization's membership list in a table nobody thinks of as one."""
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)

    client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "ana@ramapotrails.org"},
        headers={"Origin": ORIGIN},
    )

    grant = db_session.query(ConsoleTokenGrant).one()
    assert "@" not in grant.email_hash
    assert len(grant.email_hash) == 64


def test_a_request_with_no_origin_header_is_refused_before_anything_is_read(client, db_session, console_on):
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)

    response = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "a@b.org"},
    )

    assert response.status_code == 400


def test_a_token_minted_for_one_site_is_worthless_on_another(client):
    """Guard 2 again, enforced on use rather than only on mint: a stolen token
    cannot simply be pasted somewhere else."""
    token = mint_token(club_slug="ramapo-trail-conference", person_id="p1", origin=ORIGIN, permissions=["read_roster"])

    assert read_token(token, origin=ORIGIN) is not None
    assert read_token(token, origin="https://evil.example") is None


def test_a_tampered_token_is_refused(client):
    token = mint_token(club_slug="x", person_id="p1", origin=ORIGIN, permissions=["write"])
    body, signature = token.split(".", 1)

    assert read_token(f"{body}x.{signature}", origin=ORIGIN) is None
    assert read_token(f"{body}.{signature}x", origin=ORIGIN) is None
    assert read_token("not-a-token", origin=ORIGIN) is None


def test_a_token_cannot_claim_a_permission_that_is_not_one(client):
    """The permission list is filtered against the known set at mint, so a
    caller cannot smuggle a word through and have an embed honour it."""
    token = mint_token(club_slug="x", person_id="p1", origin=ORIGIN, permissions=["write", "delete_everything"])

    claims = read_token(token, origin=ORIGIN)
    assert claims is not None
    assert claims["perms"] == ["write"]


# --------------------------------------------------------------------- #
# /console/whoami - what the token in a browser's hand actually permits
# --------------------------------------------------------------------- #


def test_whoami_is_inert_until_a_deployment_switches_the_embed_on(client):
    """Same switch as the mint. Half a handshake is not a shipped feature."""
    response = client.get(
        "/console/whoami",
        headers={"Origin": ORIGIN, "Authorization": "Bearer anything"},
    )

    assert response.status_code == 503


def test_whoami_reports_the_permissions_the_server_read_out_of_the_signature(client, db_session, console_on):
    """The widget asks rather than reading the claims itself.

    Parsing the token in JavaScript would let somebody edit it in a debugger
    and change what the widget draws - which teaches a reader that the
    widget's own display is the permission check.
    """
    org, admin = _org_with_admin(db_session)
    volunteer = make_profile(db_session)
    make_assignment(db_session, org, volunteer)
    db_session.add(
        RoleInvite(
            club_id=org.id,
            email="ana@ramapotrails.org",
            claimed_by=volunteer.id,
            claimed_at="2026-09-01",
        )
    )
    db_session.commit()
    key = _make_key(client, admin.id)
    minted = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "ana@ramapotrails.org"},
        headers={"Origin": ORIGIN},
    ).json()

    response = client.get(
        "/console/whoami",
        headers={"Origin": ORIGIN, "Authorization": f"Bearer {minted['token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["org_slug"] == "ramapo-trail-conference"
    assert body["permissions"] == minted["permissions"]


def test_whoami_does_not_reissue_the_token_it_was_shown(client, db_session, console_on):
    """Reporting on a token is not extending one. A silent refresh would need
    the secret, which is the thing that must never reach a browser."""
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)
    minted = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "stranger@example.org"},
        headers={"Origin": ORIGIN},
    ).json()

    body = client.get(
        "/console/whoami",
        headers={"Origin": ORIGIN, "Authorization": f"Bearer {minted['token']}"},
    ).json()

    assert body["token"] == ""
    assert 0 < body["expires_in"] <= 900


def test_whoami_refuses_a_token_lifted_onto_another_organizations_page(client, db_session, console_on):
    """Guard 2, on use rather than only at mint."""
    _, admin = _org_with_admin(db_session)
    key = _make_key(client, admin.id)
    minted = client.post(
        "/console/session",
        json={"public_key": key["public_key"], "secret": key["secret"], "email": "stranger@example.org"},
        headers={"Origin": ORIGIN},
    ).json()

    response = client.get(
        "/console/whoami",
        headers={
            "Origin": "https://somebody-elses-site.example",
            "Authorization": f"Bearer {minted['token']}",
        },
    )

    assert response.status_code == 401


def test_every_bad_session_answers_the_same_401(client, console_on):
    """A forged signature, a missing header and a malformed string are one
    answer. Telling them apart hands somebody an oracle."""
    answers = set()
    for header in (None, "Bearer", "Bearer not.a.token", "Token abc", "Bearer " + "x" * 40):
        headers = {"Origin": ORIGIN}
        if header is not None:
            headers["Authorization"] = header
        response = client.get("/console/whoami", headers=headers)
        answers.add((response.status_code, response.json().get("detail")))

    assert answers == {(401, "That session is not valid here")}


def test_whoami_needs_an_origin_header_like_the_mint_does(client, console_on):
    response = client.get("/console/whoami", headers={"Authorization": "Bearer x"})

    assert response.status_code == 400
