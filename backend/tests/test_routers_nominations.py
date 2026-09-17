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
from app.core.sitefetch import FetchRefused
from app.core.time import utc_now
from app.core.urlguard import UrlRefused
from app.models.assist import AssistUsage
from app.models.club import Club, OrgState
from app.models.nomination import NominationContact, NominationRefusal, NominationSource, OrgNomination
from tests.factories import make_profile
from tests.nominating import MODEL_ANSWER, solved, switch_on
from tests.nominating import answers as _answers
from tests.nominating import reads as _reads
from tests.tokens import auth_headers


@pytest.fixture
def nominating(monkeypatch):
    """The deployment switched on, with the model and the fetcher stubbed."""
    return switch_on(monkeypatch)


@pytest.fixture
def reads_the_site(monkeypatch):
    _reads(monkeypatch)


@pytest.fixture
def answers(monkeypatch):
    _answers(monkeypatch)


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


class TestWhatItCostsAndWhoPays:
    """The budget, against the real `ask` rather than a stub of it.

    These moved here from tests/test_routers_assist.py when the panel moved.
    They tested a public form counted per IP address; the panel is signed in
    now, so the handle is the hiker, and that change is the point of two of
    them rather than incidental to them.
    """

    @pytest.fixture
    def api(self, monkeypatch):
        """A canned reply from the model API, costing 160 tokens a call."""
        from types import SimpleNamespace

        from app.core import assist as assist_core

        def fake_post(url, *, timeout, headers, json):
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "content": [{"type": "text", "text": MODEL_ANSWER}],
                    "usage": {"input_tokens": 120, "output_tokens": 40},
                },
            )

        monkeypatch.setattr(assist_core.httpx, "post", fake_post)

    def _read(self, client, hiker):
        return client.post(
            "/assist/nominate",
            json={"website": "https://carolinamountainclub.org", **solved(hiker.id)},
            headers=auth_headers(hiker.id),
        )

    def test_the_budget_is_counted_per_hiker(self, client, db_session, nominating, reads_the_site, api, monkeypatch):
        monkeypatch.setattr(settings, "assist_public_daily_token_budget", 100)
        hiker = make_profile(db_session)
        assert self._read(client, hiker).status_code == 200
        assert self._read(client, hiker).status_code == 429

    def test_one_hiker_spending_theirs_does_not_spend_anothers(
        self, client, db_session, nominating, reads_the_site, api, monkeypatch
    ):
        """The change sign-in bought. An address counted a whole office together.

        Two hikers behind one router used to share one budget, so the first to
        nominate a club spent the second's afternoon. This is that fixed, and
        it is the reason `counting_hash` takes a hiker rather than an address.
        """
        monkeypatch.setattr(settings, "assist_public_daily_token_budget", 100)
        mine = make_profile(db_session)
        yours = make_profile(db_session)
        assert self._read(client, mine).status_code == 200
        assert self._read(client, mine).status_code == 429
        assert self._read(client, yours).status_code == 200

    def test_one_call_may_overshoot_the_budget_and_the_next_one_cannot(
        self, client, db_session, nominating, reads_the_site, api, monkeypatch
    ):
        """The honest shape of the limit, written down rather than discovered.

        A call's cost is not knowable until it has been made, so the check is
        "have you already passed the line" rather than "would this cross it" -
        160 tokens against a 100-token budget here. Holding back a call that
        MIGHT cross the line would refuse a cheap question to somebody with
        budget left, which is the worse of the two.
        """
        monkeypatch.setattr(settings, "assist_public_daily_token_budget", 100)
        hiker = make_profile(db_session)
        self._read(client, hiker)
        spent = sum(
            row.input_tokens + row.output_tokens for row in db_session.query(AssistUsage).filter(AssistUsage.panel == "nominate")
        )
        assert spent == 160
        assert self._read(client, hiker).status_code == 429

    def test_it_stores_a_hash_and_never_the_hiker_or_their_address(self, client, db_session, nominating, reads_the_site, api):
        """Storing either would build a log of who looked up which organization.

        The address is not stored because it is no longer even read; the hiker
        is not stored because a counter does not need a name.
        """
        hiker = make_profile(db_session)
        self._read(client, hiker)
        row = db_session.query(AssistUsage).filter(AssistUsage.panel == "nominate").one()
        assert row.club_id is None
        assert len(row.client_hash) == 64
        assert hiker.id not in row.client_hash
        assert "." not in row.client_hash


class TestWhatTheGuardRefusesBeforeAnythingIsSpent:
    """Moved from tests/test_routers_assist.py, and answering differently now.

    These used to be 422s from the schema: `website` was a string the schema
    itself policed. The refusal now comes from `app/core/urlguard.py`, which
    is the better home - one module decides what this server may open, rather
    than every route that takes an address deciding again - so it is a 400.

    `read_site` is deliberately NOT stubbed here. The whole point is that the
    real guard runs, and every one of these is refused before DNS is asked.
    """

    @pytest.mark.parametrize(
        "hostile",
        [
            "javascript:alert(1)",
            "data:text/html,x",
            "file:///etc/passwd",
            "ftp://example.org/pub",
            "https://169.254.169.254/latest/meta-data/",
            "https://wiki.local/",
            "https://intranet/",
            "write me a poem about anything",
        ],
    )
    def test_it_is_refused_without_a_fetch(self, client, db_session, nominating, hostile):
        hiker = make_profile(db_session)
        response = client.post(
            "/assist/nominate",
            json={"website": hostile, **solved(hiker.id)},
            headers=auth_headers(hiker.id),
        )
        assert response.status_code == 400

    def test_nothing_is_spent_on_a_refusal(self, client, db_session, nominating):
        """The guard runs before the model does, so a refusal is free."""
        hiker = make_profile(db_session)
        client.post(
            "/assist/nominate",
            json={"website": "file:///etc/passwd", **solved(hiker.id)},
            headers=auth_headers(hiker.id),
        )
        assert db_session.query(AssistUsage).count() == 0
