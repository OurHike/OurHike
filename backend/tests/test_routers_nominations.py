"""The nominate flow end to end, and the four gates in front of it.

`POST /assist/nominate` used to take a website from anybody on the internet,
send it to a model with no tools, and let the marketing page render the reply
under "WHAT WE COULD SEE ON THEIR SITE". Nothing had been opened. The
maintainer's 2026-09-17 decision made the reading real and put three bounds
in front of it; this file is what keeps them there.

**Signed in** - the panel is not public any more.
**A solved challenge** - so one account cannot drive it in a loop.
**A guard on the address** - so it is not a fetcher pointed wherever a
stranger says.
**And a budget** - which was always here and is now the third bound rather
than the only one.

The fifth property is the one the flow exists for and is not a gate:
**nothing the reading proposed is stored until the hiker keeps it.** A
contact the hiker dropped has no row, which is the maintainer's condition on
harvesting people's addresses implemented rather than displayed.

Nothing here reaches the network: the fetcher and the model are both
injected.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.core.challenge import issue, solve
from app.core.sitefetch import FetchRefused, Link, Page
from app.core.time import utc_now
from app.core.urlguard import UrlRefused
from app.models.club import Club, OrgState
from app.models.nomination import NominationContact, NominationRefusal, NominationSource, OrgNomination
from tests.factories import make_profile
from tests.tokens import auth_headers

SECRET = "a challenge secret for the tests"

CONTACT_PAGE = Page(
    url="https://carolinamountainclub.org/get-involved",
    title="Get Involved - Carolina Mountain Club",
    text=(
        "Volunteer coordinator Dale Whitford - volunteers@carolinamountainclub.org. "
        "Trail data: Priya Raghavan, maps@carolinamountainclub.org. "
        "Our layer is at https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0"
    ),
    links=(Link(href="mailto:volunteers@carolinamountainclub.org", text="Dale Whitford"),),
    emails=("volunteers@carolinamountainclub.org", "maps@carolinamountainclub.org"),
)

MODEL_ANSWER = """{
  "org_name": "Carolina Mountain Club",
  "summary": "Asheville, NC.",
  "sources": [{"label": "ArcGIS FeatureServer",
               "url": "https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0",
               "verdict": "usable", "detail": "line features"}],
  "contacts": [
    {"name": "Dale Whitford", "role": "Volunteer coordinator",
     "email": "volunteers@carolinamountainclub.org",
     "source_page": "https://carolinamountainclub.org/get-involved"},
    {"name": "Board President", "role": "Leadership",
     "email": "president@carolinamountainclub.org",
     "source_page": "https://carolinamountainclub.org/contact"}
  ]
}"""


@pytest.fixture
def nominating(monkeypatch):
    """The deployment switched on, with the model and the fetcher stubbed."""
    monkeypatch.setattr(settings, "nominate_challenge_secret", SECRET)
    monkeypatch.setattr(settings, "nominate_challenge_difficulty", 12)
    monkeypatch.setattr(settings, "assist_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-not-a-real-key")
    return settings


@pytest.fixture
def reads_the_site(monkeypatch):
    from app.routers import nominations as router

    monkeypatch.setattr(router, "read_site", lambda website, **kw: (CONTACT_PAGE,))
    return router


@pytest.fixture
def answers(monkeypatch):
    from types import SimpleNamespace

    from app.core import assist as assist_core

    def fake_ask(db, *, panel, system, prompt, club=None, client_address=None):
        return SimpleNamespace(text=MODEL_ANSWER, input_tokens=100, output_tokens=50)

    from app.routers import nominations as router

    monkeypatch.setattr(router, "ask", fake_ask)
    return assist_core


def solved(hiker_id: str, difficulty: int = 12) -> dict:
    challenge = issue(hiker_id, secret=SECRET, now=int(utc_now().timestamp()), difficulty=difficulty)
    return {
        "nonce": challenge.nonce,
        "difficulty": challenge.difficulty,
        "expires_at": challenge.expires_at,
        "signature": challenge.signature,
        "solution": solve(challenge),
    }


class TestTheGatesInFront:
    def test_a_signed_out_visitor_cannot_ask_for_a_challenge(self, client, nominating):
        assert client.get("/assist/nominate/challenge").status_code == 401

    def test_a_signed_out_visitor_cannot_make_us_fetch_anything(self, client, db_session, nominating, reads_the_site):
        fetched: list[str] = []
        response = client.post(
            "/assist/nominate",
            json={"website": "https://carolinamountainclub.org", **solved("anybody")},
        )
        assert response.status_code == 401
        assert fetched == []

    def test_a_deployment_with_no_challenge_secret_refuses_rather_than_minting_one(self, client, db_session, monkeypatch):
        """An empty secret would sign challenges anybody could also sign."""
        monkeypatch.setattr(settings, "nominate_challenge_secret", "")
        hiker = make_profile(db_session)
        response = client.get("/assist/nominate/challenge", headers=auth_headers(hiker.id))
        assert response.status_code == 503

    def test_an_unsolved_challenge_does_not_get_a_fetch(self, client, db_session, nominating, reads_the_site, answers):
        hiker = make_profile(db_session)
        payload = solved(hiker.id)
        payload["solution"] = "0"
        response = client.post(
            "/assist/nominate",
            json={"website": "https://carolinamountainclub.org", **payload},
            headers=auth_headers(hiker.id),
        )
        assert response.status_code == 409

    def test_one_hikers_challenge_is_not_anothers(self, client, db_session, nominating, reads_the_site, answers):
        mine = make_profile(db_session)
        yours = make_profile(db_session)
        response = client.post(
            "/assist/nominate",
            json={"website": "https://carolinamountainclub.org", **solved(yours.id)},
            headers=auth_headers(mine.id),
        )
        assert response.status_code == 409

    def test_a_challenge_is_good_once(self, client, db_session, nominating, reads_the_site, answers):
        hiker = make_profile(db_session)
        payload = {"website": "https://carolinamountainclub.org", **solved(hiker.id)}
        assert client.post("/assist/nominate", json=payload, headers=auth_headers(hiker.id)).status_code == 200
        again = client.post("/assist/nominate", json=payload, headers=auth_headers(hiker.id))
        assert again.status_code == 409

    def test_an_address_the_guard_refuses_is_a_400_and_never_a_reading(
        self, client, db_session, nominating, answers, monkeypatch
    ):
        from app.routers import nominations as router

        def refuse(website, **kw):
            raise UrlRefused("wiki.local is a private network name.")

        monkeypatch.setattr(router, "read_site", refuse)
        hiker = make_profile(db_session)
        response = client.post(
            "/assist/nominate",
            json={"website": "https://wiki.local", **solved(hiker.id)},
            headers=auth_headers(hiker.id),
        )
        assert response.status_code == 400

    def test_a_site_that_would_not_answer_is_a_502_rather_than_an_empty_reading(
        self, client, db_session, nominating, answers, monkeypatch
    ):
        """An empty reading renders as "this club publishes nothing"."""
        from app.routers import nominations as router

        def refuse(website, **kw):
            raise FetchRefused("carolinamountainclub.org answered 500.", status=500)

        monkeypatch.setattr(router, "read_site", refuse)
        hiker = make_profile(db_session)
        response = client.post(
            "/assist/nominate",
            json={"website": "https://carolinamountainclub.org", **solved(hiker.id)},
            headers=auth_headers(hiker.id),
        )
        assert response.status_code == 502


class TestTheReading:
    def test_it_comes_back_with_what_was_on_the_page(self, client, db_session, nominating, reads_the_site, answers):
        hiker = make_profile(db_session)
        response = client.post(
            "/assist/nominate",
            json={"website": "https://carolinamountainclub.org", **solved(hiker.id)},
            headers=auth_headers(hiker.id),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["read_at_all"] is True
        assert body["org_name"] == "Carolina Mountain Club"
        assert [c["email"] for c in body["contacts"]] == ["volunteers@carolinamountainclub.org"]

    def test_the_invented_contact_never_reaches_the_hiker(self, client, db_session, nominating, reads_the_site, answers):
        """`president@` is in the model's answer and on no page we read.

        The whole flow's worst outcome is emailing it, and this is where that
        is stopped - before a hiker sees it and keeps it in good faith.
        """
        hiker = make_profile(db_session)
        response = client.post(
            "/assist/nominate",
            json={"website": "https://carolinamountainclub.org", **solved(hiker.id)},
            headers=auth_headers(hiker.id),
        )
        addresses = [c["email"] for c in response.json()["contacts"]]
        assert "president@carolinamountainclub.org" not in addresses

    def test_the_reading_writes_nothing_down(self, client, db_session, nominating, reads_the_site, answers):
        """The maintainer's condition, as a row count rather than a promise."""
        hiker = make_profile(db_session)
        client.post(
            "/assist/nominate",
            json={"website": "https://carolinamountainclub.org", **solved(hiker.id)},
            headers=auth_headers(hiker.id),
        )
        assert db_session.query(NominationContact).count() == 0
        assert db_session.query(NominationSource).count() == 0
        assert db_session.query(OrgNomination).count() == 0


def a_submission(**overrides):
    payload = {
        "website": "https://carolinamountainclub.org",
        "org_name": "Carolina Mountain Club",
        "region": "Asheville, NC",
        "sources": [
            {
                "label": "ArcGIS FeatureServer",
                "url": "https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0",
                "verdict": "usable",
                "proposed_by": "reading",
            }
        ],
        "contacts": [
            {
                "name": "Dale Whitford",
                "role": "Volunteer coordinator",
                "email": "volunteers@carolinamountainclub.org",
                "source_page": "https://carolinamountainclub.org/get-involved",
                "proposed_by": "reading",
            },
            {
                "name": "Priya Raghavan",
                "role": "GIS",
                "email": "maps@carolinamountainclub.org",
                "source_page": "https://carolinamountainclub.org/get-involved",
                "proposed_by": "reading",
            },
            {
                "name": None,
                "role": "Board",
                "email": "board@carolinamountainclub.org",
                "source_page": "https://carolinamountainclub.org/contact",
                "proposed_by": "hiker",
            },
        ],
    }
    payload.update(overrides)
    return payload


class TestSubmitting:
    def test_only_what_the_hiker_sent_is_stored(self, client, db_session):
        hiker = make_profile(db_session)
        response = client.post("/clubs/nominations", json=a_submission(), headers=auth_headers(hiker.id))
        assert response.status_code == 201
        stored = {c.email for c in db_session.query(NominationContact).all()}
        assert stored == {
            "volunteers@carolinamountainclub.org",
            "maps@carolinamountainclub.org",
            "board@carolinamountainclub.org",
        }

    def test_who_proposed_each_line_survives(self, client, db_session):
        """A club asking "who said this about us" gets the answer per line."""
        hiker = make_profile(db_session)
        client.post("/clubs/nominations", json=a_submission(), headers=auth_headers(hiker.id))
        by_email = {c.email: c.proposed_by.value for c in db_session.query(NominationContact).all()}
        assert by_email["board@carolinamountainclub.org"] == "hiker"
        assert by_email["volunteers@carolinamountainclub.org"] == "reading"

    def test_the_org_arrives_unclaimed(self, client, db_session):
        hiker = make_profile(db_session)
        client.post("/clubs/nominations", json=a_submission(), headers=auth_headers(hiker.id))
        club = db_session.query(Club).filter(Club.name == "Carolina Mountain Club").one()
        assert club.state == OrgState.unclaimed

    def test_a_signed_out_visitor_cannot_submit(self, client, db_session):
        assert client.post("/clubs/nominations", json=a_submission()).status_code == 401

    def test_a_nomination_with_nobody_to_ask_is_refused(self, client, db_session):
        hiker = make_profile(db_session)
        response = client.post("/clubs/nominations", json=a_submission(contacts=[]), headers=auth_headers(hiker.id))
        assert response.status_code == 422

    def test_a_club_that_said_never_again_is_not_nominated_twice(self, client, db_session):
        """Checked before a row is written and before anybody there is written to."""
        db_session.add(NominationRefusal(domain="carolinamountainclub.org"))
        db_session.commit()
        hiker = make_profile(db_session)
        response = client.post("/clubs/nominations", json=a_submission(), headers=auth_headers(hiker.id))
        assert response.status_code == 409
        assert db_session.query(OrgNomination).count() == 0


class TestTheClubsOwnScreen:
    def _submit(self, client, db_session):
        hiker = make_profile(db_session)
        client.post("/clubs/nominations", json=a_submission(), headers=auth_headers(hiker.id))
        return db_session.query(OrgNomination).one()

    def test_the_link_needs_no_account(self, client, db_session):
        nomination = self._submit(client, db_session)
        response = client.get(f"/nominations/{nomination.proposal_token}")
        assert response.status_code == 200
        assert response.json()["org_name"] == "Carolina Mountain Club"

    def test_a_token_nobody_issued_is_a_404(self, client, db_session):
        assert client.get("/nominations/not-a-real-token").status_code == 404

    def test_the_club_is_never_told_who_proposed_them(self, client, db_session):
        """And the design says the other direction too: Sam is not told who declined."""
        nomination = self._submit(client, db_session)
        body = client.get(f"/nominations/{nomination.proposal_token}").json()
        assert body["proposed_by_display"] == "A hiker on OurHike"
        assert "@" not in body["proposed_by_display"]

    def test_three_approvals_are_needed(self, client, db_session):
        nomination = self._submit(client, db_session)
        token = nomination.proposal_token
        for expected in ("proposed", "proposed", "accepted"):
            body = client.post(f"/nominations/{token}/decision", json={"approve": True}).json()
            assert body["state"] == expected

    def test_one_refusal_stops_it(self, client, db_session):
        """Asymmetric on purpose: a club should not have to say no three times."""
        nomination = self._submit(client, db_session)
        body = client.post(f"/nominations/{nomination.proposal_token}/decision", json={"approve": False}).json()
        assert body["state"] == "declined"

    def test_declining_puts_the_org_row_beyond_reach(self, client, db_session):
        nomination = self._submit(client, db_session)
        client.post(f"/nominations/{nomination.proposal_token}/decision", json={"approve": False})
        db_session.expire_all()
        club = db_session.query(Club).filter(Club.id == nomination.club_id).one()
        assert club.state == OrgState.deleted

    def test_never_ask_again_is_written_down_for_next_time(self, client, db_session):
        nomination = self._submit(client, db_session)
        client.post(
            f"/nominations/{nomination.proposal_token}/decision",
            json={"approve": False, "never_ask_again": True, "note": "Please do not"},
        )
        assert db_session.query(NominationRefusal).filter(NominationRefusal.domain == "carolinamountainclub.org").count() == 1

    def test_declining_without_never_ask_again_leaves_the_door_open(self, client, db_session):
        """They said no to this proposal, not to the idea. Those differ."""
        nomination = self._submit(client, db_session)
        client.post(f"/nominations/{nomination.proposal_token}/decision", json={"approve": False})
        assert db_session.query(NominationRefusal).count() == 0

    def test_an_answered_proposal_cannot_be_answered_again(self, client, db_session):
        nomination = self._submit(client, db_session)
        token = nomination.proposal_token
        client.post(f"/nominations/{token}/decision", json={"approve": False})
        again = client.post(f"/nominations/{token}/decision", json={"approve": True})
        assert again.status_code == 409

    def test_an_expired_link_says_the_same_thing_as_a_wrong_one(self, client, db_session):
        """A distinguishing error is an oracle for guessing tokens."""
        import datetime as dt

        nomination = self._submit(client, db_session)
        nomination.token_expires_at = utc_now() - dt.timedelta(days=1)
        db_session.commit()
        expired = client.get(f"/nominations/{nomination.proposal_token}")
        invented = client.get("/nominations/not-a-real-token")
        assert expired.status_code == invented.status_code == 404
        assert expired.json()["detail"] == invented.json()["detail"]
