"""Sending mail to people who never asked to hear from us.

Until 2026-09-17 this repository sent no mail at all. The nominate flow needs
it - a hiker offers a club's trails and three people at that club have to be
asked - and the maintainer chose to build sending properly rather than hand
the hiker a `mailto:`.

**COLD MAIL ABOUT SOMEBODY'S OWN DATA IS THE HARDEST KIND TO SEND WELL**, and
these tests are the whole of what makes it defensible. Four properties, each
of which is a promise rather than a preference:

1. **Off unless switched on.** A preview deployment holding a fixture with a
   real club's address must not be one environment variable away from mailing
   them. Default off, and an allow-list for everywhere that is not
   production.
2. **The suppression list is checked on the send path, never by the caller.**
   A promise each caller has to remember is a promise that lasts until the
   second caller.
3. **A bounce or a complaint writes a suppression.** Otherwise the list
   records what happened and does not prevent it happening again.
4. **Every message says how to stop it**, in a header a mail client can act
   on without a person reading anything.
"""

import pytest

from app.core.mail import (
    MailDisabled,
    MailFailed,
    MailSuppressed,
    is_suppressed,
    record_delivery_failure,
    send,
    suppress,
)
from app.models.mail import EmailSend, EmailSuppression, MailPurpose, MailState, SuppressionReason


class Provider:
    """A stand-in for SES that remembers what it was handed."""

    def __init__(self, *, fails: Exception | None = None, message_id: str = "ses-1") -> None:
        self.sent: list[dict] = []
        self.fails = fails
        self.message_id = message_id

    def send_email(self, **kwargs):
        if self.fails:
            raise self.fails
        self.sent.append(kwargs)
        return {"MessageId": self.message_id}


def a_message(**overrides):
    payload = {
        "to": "volunteers@carolinamountainclub.org",
        "purpose": MailPurpose.nomination_proposal,
        "subject": "A hiker has offered to put your trails on OurHike",
        "body_text": "Somebody proposed adding your trails. Nothing has been published.",
        "unsubscribe_url": "https://ourhike.org/n/abc123/no-thank-you",
    }
    payload.update(overrides)
    return payload


class TestOffUnlessSwitchedOn:
    def test_nothing_is_sent_when_mail_is_not_enabled(self, db_session):
        provider = Provider()
        with pytest.raises(MailDisabled):
            send(db_session, provider=provider, enabled=False, **a_message())
        assert provider.sent == []

    def test_nothing_is_written_down_when_mail_is_not_enabled(self, db_session):
        """A log of messages nobody sent is a log that misleads a reader."""
        with pytest.raises(MailDisabled):
            send(db_session, provider=Provider(), enabled=False, **a_message())
        assert db_session.query(EmailSend).count() == 0

    def test_an_allow_list_confines_a_non_production_environment(self, db_session):
        """UA has to be able to exercise this without reaching a real club."""
        provider = Provider()
        with pytest.raises(MailDisabled):
            send(
                db_session,
                provider=provider,
                enabled=True,
                allowed=("@ourhike.org",),
                **a_message(),
            )
        assert provider.sent == []

    def test_the_allow_list_lets_its_own_addresses_through(self, db_session):
        provider = Provider()
        send(
            db_session,
            provider=provider,
            enabled=True,
            allowed=("@ourhike.org",),
            **a_message(to="test@ourhike.org"),
        )
        assert len(provider.sent) == 1

    def test_no_allow_list_means_anywhere(self, db_session):
        provider = Provider()
        send(db_session, provider=provider, enabled=True, allowed=(), **a_message())
        assert len(provider.sent) == 1


class TestTheSuppressionList:
    def test_a_suppressed_address_is_never_written_to(self, db_session):
        suppress(db_session, "volunteers@carolinamountainclub.org", SuppressionReason.refused)
        db_session.commit()
        provider = Provider()
        with pytest.raises(MailSuppressed):
            send(db_session, provider=provider, enabled=True, **a_message())
        assert provider.sent == []

    def test_the_check_does_not_care_about_case(self, db_session):
        """`Maps@Club.org` and `maps@club.org` are one mailbox."""
        suppress(db_session, "Volunteers@CarolinaMountainClub.ORG", SuppressionReason.bounced)
        db_session.commit()
        with pytest.raises(MailSuppressed):
            send(db_session, provider=Provider(), enabled=True, **a_message())

    def test_suppressing_twice_is_not_an_error(self, db_session):
        """A second bounce must not fail the handler that is recording it."""
        suppress(db_session, "a@club.org", SuppressionReason.bounced)
        suppress(db_session, "a@club.org", SuppressionReason.complained)
        db_session.commit()
        assert db_session.query(EmailSuppression).count() == 1

    def test_the_first_reason_is_kept(self, db_session):
        """Why somebody first said stop is the more useful fact."""
        suppress(db_session, "a@club.org", SuppressionReason.refused)
        suppress(db_session, "a@club.org", SuppressionReason.bounced)
        db_session.commit()
        row = db_session.query(EmailSuppression).one()
        assert row.reason == SuppressionReason.refused

    def test_is_suppressed_answers_without_a_send(self, db_session):
        suppress(db_session, "a@club.org", SuppressionReason.manual)
        db_session.commit()
        assert is_suppressed(db_session, "A@Club.org") is True
        assert is_suppressed(db_session, "b@club.org") is False


class TestTheLog:
    def test_a_sent_message_records_the_providers_own_id(self, db_session):
        """It is the only handle a deliverability question can be chased with."""
        send(db_session, provider=Provider(message_id="0100-abc"), enabled=True, **a_message())
        db_session.commit()
        row = db_session.query(EmailSend).one()
        assert row.state == MailState.sent
        assert row.provider_message_id == "0100-abc"
        assert row.sent_at is not None

    def test_a_provider_failure_is_recorded_rather_than_lost(self, db_session):
        with pytest.raises(MailFailed):
            send(
                db_session,
                provider=Provider(fails=RuntimeError("throttled")),
                enabled=True,
                **a_message(),
            )
        db_session.commit()
        row = db_session.query(EmailSend).one()
        assert row.state == MailState.failed
        assert "throttled" in (row.error or "")

    def test_the_log_keeps_the_subject_and_not_the_body(self, db_session):
        """A club asking what we sent deserves an answer, not a transcript."""
        send(db_session, provider=Provider(), enabled=True, **a_message())
        db_session.commit()
        row = db_session.query(EmailSend).one()
        assert "offered to put your trails" in row.subject
        assert not hasattr(row, "body_text")

    def test_the_address_is_stored_as_it_will_be_matched(self, db_session):
        send(db_session, provider=Provider(), enabled=True, **a_message(to="Maps@CMC.org"))
        db_session.commit()
        assert db_session.query(EmailSend).one().to_address == "maps@cmc.org"


class TestBouncesAndComplaints:
    def test_a_bounce_suppresses_the_address(self, db_session):
        row = send(db_session, provider=Provider(message_id="m-1"), enabled=True, **a_message())
        db_session.commit()
        record_delivery_failure(db_session, "m-1", MailState.bounced)
        db_session.commit()
        db_session.refresh(row)
        assert row.state == MailState.bounced
        assert is_suppressed(db_session, "volunteers@carolinamountainclub.org") is True

    def test_a_complaint_suppresses_the_address(self, db_session):
        send(db_session, provider=Provider(message_id="m-2"), enabled=True, **a_message())
        db_session.commit()
        record_delivery_failure(db_session, "m-2", MailState.complained)
        db_session.commit()
        assert is_suppressed(db_session, "volunteers@carolinamountainclub.org") is True

    def test_a_notice_about_a_message_we_have_no_record_of_is_ignored(self, db_session):
        """Provider webhooks are replayed, reordered and occasionally fictional."""
        record_delivery_failure(db_session, "never-heard-of-it", MailState.bounced)
        db_session.commit()
        assert db_session.query(EmailSuppression).count() == 0


class TestWhatGoesOnTheWire:
    def test_every_message_says_how_to_stop_it(self, db_session):
        """RFC 8058, so a mail client can offer it without anybody reading."""
        provider = Provider()
        send(db_session, provider=provider, enabled=True, **a_message())
        raw = provider.sent[0]["Content"]["Raw"]["Data"].decode()
        assert "List-Unsubscribe: <https://ourhike.org/n/abc123/no-thank-you>" in raw
        assert "List-Unsubscribe-Post: List-Unsubscribe=One-Click" in raw

    def test_a_message_with_nowhere_to_unsubscribe_cannot_even_be_called(self):
        """Not an oversight to tolerate: it is the one header that must be there.

        A required keyword rather than a runtime check, so a caller that
        forgets it does not compile rather than not sending - `TypeError` is
        the stronger refusal and the test says which one it is getting.
        """
        payload = a_message()
        payload.pop("unsubscribe_url")
        with pytest.raises(TypeError, match="unsubscribe_url"):
            send(None, provider=Provider(), enabled=True, **payload)

    @pytest.mark.parametrize("empty", ["", "   "])
    def test_an_empty_unsubscribe_url_is_refused_before_anything_is_written(self, db_session, empty):
        """The keyword being present is not the same as it pointing anywhere."""
        with pytest.raises(ValueError):
            send(db_session, provider=Provider(), enabled=True, **a_message(unsubscribe_url=empty))
        assert db_session.query(EmailSend).count() == 0

    def test_the_reply_address_is_a_mailbox_a_person_reads(self, db_session):
        provider = Provider()
        send(
            db_session,
            provider=provider,
            enabled=True,
            sender="OurHike <hello@ourhike.org>",
            reply_to="hello@ourhike.org",
            **a_message(),
        )
        raw = provider.sent[0]["Content"]["Raw"]["Data"].decode()
        assert "Reply-To: hello@ourhike.org" in raw

    def test_the_subject_cannot_smuggle_a_header(self, db_session):
        """A club's own name reaches this field, and a newline in it is an injection.

        Asserted on where the line STARTS rather than on the text appearing
        anywhere: the sanitised subject still contains those words, harmlessly,
        and a substring check would pass for the wrong reason the day the
        sanitising broke.
        """
        provider = Provider()
        send(
            db_session,
            provider=provider,
            enabled=True,
            **a_message(subject="Hello\r\nBcc: everybody@example.org"),
        )
        raw = provider.sent[0]["Content"]["Raw"]["Data"].decode()
        assert not any(line.startswith("Bcc:") for line in raw.splitlines())

    def test_an_address_that_is_not_an_address_is_refused_before_anything_is_written(self, db_session):
        with pytest.raises(ValueError):
            send(db_session, provider=Provider(), enabled=True, **a_message(to="not an address"))
        assert db_session.query(EmailSend).count() == 0
