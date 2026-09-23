"""Asking three people at a club about a nomination, once each.

`app/core/mail.py` is how anything is sent. This is what gets said, to whom,
and what happens when one of them bounces - the part where a defensible cold
email becomes an indefensible one if it is got wrong.

**THE MESSAGE HAS TO SURVIVE BEING READ BY A STRANGER WHO IS ANNOYED.**
Somebody at a trail club opens it having never heard of OurHike, about their
own data, from a hiker they do not know. So four things are asserted about
every message rather than left to a template nobody re-reads: it names the
organization it is about, it says nothing has been published, it carries the
link that stops it forever, and it does not name the hiker who proposed them.

**AND IT IS SENT ONCE.** A second run over the same nomination must not write
to the same three people twice - the loudest possible way to turn a
reasonable ask into a complaint.
"""

import pytest

from app.core.mail import MailDisabled
from app.core.nomination_mail import ask_the_club
from app.models.mail import EmailSend, MailPurpose, MailState, SuppressionReason
from app.models.nomination import NominationState


class Provider:
    def __init__(self, *, fail_for: str | None = None) -> None:
        self.sent: list[dict] = []
        self.fail_for = fail_for

    def send_email(self, **kwargs):
        to = kwargs["Destination"]["ToAddresses"][0]
        if self.fail_for and to == self.fail_for:
            raise RuntimeError("550 no such mailbox")
        self.sent.append(kwargs)
        return {"MessageId": f"ses-{len(self.sent)}"}


def bodies(provider: Provider) -> list[str]:
    return [call["Content"]["Raw"]["Data"].decode() for call in provider.sent]


@pytest.fixture
def nomination(db_session, client):
    """One submitted nomination with three contacts, via the real endpoint."""
    from tests.factories import make_profile
    from tests.test_routers_nominations import a_submission
    from tests.tokens import auth_headers

    hiker = make_profile(db_session)
    client.post("/clubs/nominations", json=a_submission(), headers=auth_headers(hiker.id))
    from app.models.nomination import OrgNomination

    return db_session.query(OrgNomination).one()


class TestWhoIsWrittenTo:
    def test_every_contact_the_hiker_kept(self, db_session, nomination):
        provider = Provider()
        ask_the_club(db_session, nomination, provider=provider, enabled=True)
        db_session.commit()
        assert len(provider.sent) == 3

    def test_each_of_them_once(self, db_session, nomination):
        provider = Provider()
        ask_the_club(db_session, nomination, provider=provider, enabled=True)
        db_session.commit()
        addresses = [call["Destination"]["ToAddresses"][0] for call in provider.sent]
        assert len(set(addresses)) == 3

    def test_running_it_twice_does_not_write_to_anybody_twice(self, db_session, nomination):
        """The loudest way to turn a reasonable ask into a complaint."""
        provider = Provider()
        ask_the_club(db_session, nomination, provider=provider, enabled=True)
        db_session.commit()
        ask_the_club(db_session, nomination, provider=provider, enabled=True)
        db_session.commit()
        assert len(provider.sent) == 3

    def test_a_suppressed_address_is_skipped_and_the_others_still_go(self, db_session, nomination):
        from app.core.mail import suppress

        suppress(db_session, "maps@carolinamountainclub.org", SuppressionReason.refused)
        db_session.commit()
        provider = Provider()
        ask_the_club(db_session, nomination, provider=provider, enabled=True)
        db_session.commit()
        addresses = [call["Destination"]["ToAddresses"][0] for call in provider.sent]
        assert "maps@carolinamountainclub.org" not in addresses
        assert len(addresses) == 2

    def test_one_failure_does_not_stop_the_others(self, db_session, nomination):
        provider = Provider(fail_for="maps@carolinamountainclub.org")
        ask_the_club(db_session, nomination, provider=provider, enabled=True)
        db_session.commit()
        assert len(provider.sent) == 2
        failed = db_session.query(EmailSend).filter(EmailSend.state == MailState.failed).one()
        assert failed.to_address == "maps@carolinamountainclub.org"

    def test_nothing_is_sent_when_mail_is_off(self, db_session, nomination):
        provider = Provider()
        ask_the_club(db_session, nomination, provider=provider, enabled=False)
        db_session.commit()
        assert provider.sent == []
        assert db_session.query(EmailSend).count() == 0

    def test_it_says_so_rather_than_claiming_the_club_was_asked(self, db_session, nomination):
        """A nomination that reads `emailed` with nothing sent is a lie in a column."""
        ask_the_club(db_session, nomination, provider=Provider(), enabled=False)
        db_session.commit()
        db_session.refresh(nomination)
        assert nomination.state == NominationState.proposed
        assert nomination.emailed_at is None

    def test_a_sent_nomination_records_that_it_was(self, db_session, nomination):
        ask_the_club(db_session, nomination, provider=Provider(), enabled=True)
        db_session.commit()
        db_session.refresh(nomination)
        assert nomination.state == NominationState.emailed
        assert nomination.emailed_at is not None


class TestWhatItSays:
    def _bodies(self, db_session, nomination):
        provider = Provider()
        ask_the_club(db_session, nomination, provider=provider, enabled=True)
        db_session.commit()
        return bodies(provider)

    def test_it_names_the_organization_it_is_about(self, db_session, nomination):
        """Otherwise it reads as spam about nothing in particular."""
        for body in self._bodies(db_session, nomination):
            assert "Carolina Mountain Club" in body

    def test_it_says_nothing_has_been_published(self, db_session, nomination):
        """The single most important sentence in it, and the first worry."""
        for body in self._bodies(db_session, nomination):
            assert "nothing has been published" in body.lower()

    def test_it_carries_the_link_that_stops_it_forever(self, db_session, nomination):
        for body in self._bodies(db_session, nomination):
            assert "List-Unsubscribe:" in body
            assert "no-thank-you" in body

    def test_each_message_carries_its_own_contacts_link_and_never_the_shared_one(self, db_session, nomination):
        """#1635: one shared link let whoever held it cast every decision.

        Each person's message carries their own `decision_token`, so an
        answer through it is theirs and counts once.
        """
        from app.models.nomination import NominationContact

        provider = Provider()
        ask_the_club(db_session, nomination, provider=provider, enabled=True)
        db_session.commit()
        tokens = {
            contact.email: contact.decision_token
            for contact in db_session.query(NominationContact).filter(NominationContact.nomination_id == nomination.id)
        }
        for call in provider.sent:
            to = call["Destination"]["ToAddresses"][0]
            body = call["Content"]["Raw"]["Data"].decode()
            assert tokens[to] in body
            assert nomination.proposal_token not in body

    def test_it_does_not_name_the_hiker_who_proposed_them(self, db_session, nomination):
        """The design is explicit in both directions.

        The club is not handed a way to contact the hiker, and the hiker is
        never told who declined. A name in this message is the first half of
        that promise broken, and the nominating hiker is a volunteer doing a
        stranger a favour rather than somebody who signed up to be contacted
        by a club they have no relationship with.
        """
        from app.models.profile import Profile

        proposer = db_session.query(Profile).filter(Profile.id == nomination.nominated_by).one()
        for body in self._bodies(db_session, nomination):
            assert nomination.nominated_by not in body
            if proposer.display_name:
                assert proposer.display_name not in body

    def test_it_is_logged_as_what_it_is(self, db_session, nomination):
        ask_the_club(db_session, nomination, provider=Provider(), enabled=True)
        db_session.commit()
        rows = db_session.query(EmailSend).all()
        assert {row.purpose for row in rows} == {MailPurpose.nomination_proposal}
        assert all(row.nomination_id == nomination.id for row in rows)


class TestTheEnvironmentGuard:
    def test_an_allow_list_confines_it_and_says_which_addresses_it_kept(self, db_session, nomination):
        """UA has to exercise this end to end without reaching a real club."""
        provider = Provider()
        ask_the_club(
            db_session,
            nomination,
            provider=provider,
            enabled=True,
            allowed=("@ourhike.org",),
        )
        db_session.commit()
        assert provider.sent == []
        db_session.refresh(nomination)
        assert nomination.state == NominationState.proposed

    def test_mail_disabled_is_not_swallowed_as_success(self, db_session, nomination):
        result = ask_the_club(db_session, nomination, provider=Provider(), enabled=False)
        assert result.sent == 0
        assert result.blocked >= 3
        assert isinstance(result.reasons[0], MailDisabled)
