"""What we say to three people at a club who have never heard of us.

`app/core/mail.py` is how anything is sent and carries the four promises that
make sending defensible at all. This is what gets said, to whom, and once.

**THE MESSAGE IS WRITTEN FOR SOMEBODY ANNOYED TO RECEIVE IT.** A volunteer at
a trail club opens it having never heard of OurHike, about their own data,
proposed by a hiker they do not know. Four things are in every one of them and
are asserted in tests/test_nomination_mail.py rather than left to a template
nobody re-reads: it names the organization, it says nothing has been
published, it carries the link that stops it forever, and it does not name the
hiker.

**IT DOES NOT NAME THE HIKER, in either direction.** The design is explicit
that the club is not handed a way to contact whoever proposed them and that
the hiker is never told who declined. The person who nominated a club is a
volunteer doing a stranger a favour; putting their name in front of an
organization that may be irritated is not part of the favour.

**IT IS SENT ONCE.** `_already_written_to` reads the send log rather than
trusting a state column, because the two can disagree - a run that sent two of
three and then failed leaves a nomination that is neither `proposed` nor
safely re-sendable. Writing to the same three people twice is the loudest
available way to turn a reasonable ask into a complaint.

**AND A REFUSAL IS NOT A SUCCESS.** `ask_the_club` returns what happened
rather than raising or shrugging, and leaves the nomination at `proposed` when
nothing went. A nomination reading `emailed` with nothing sent is a lie in a
column, and the thing a maintainer would rely on to decide it needs no
follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import settings
from app.core.mail import MailDisabled, MailFailed, MailSuppressed, send
from app.core.time import utc_now
from app.models.club import Club
from app.models.mail import EmailSend, MailPurpose, MailState
from app.models.nomination import (
    NominationContact,
    NominationSource,
    NominationState,
    OrgNomination,
)

# Where the club's own screen lives. The app serves it, because it is a
# rendered page rather than an API response and the person opening it has no
# account - see app/routers/nominations.py's note on the token.
PROPOSAL_PATH = "/app/n/{token}"
REFUSE_PATH = "/app/n/{token}/no-thank-you"


@dataclass
class Asked:
    """What one attempt at asking a club actually did.

    Counted rather than boolean because the interesting cases are partial: two
    of three sent, one suppressed, one bounced. A caller deciding whether to
    tell a maintainer needs the shape rather than a yes.
    """

    sent: int = 0
    blocked: int = 0
    reasons: list[Exception] = field(default_factory=list)


def _already_written_to(db: Session, nomination: OrgNomination) -> set[str]:
    """Addresses this nomination has already produced a message for.

    Read from the send log rather than from `nomination.state`, because a run
    that sent two of three and then failed leaves those two written to and the
    nomination still `proposed`. Trusting the column would write to them again.
    A `failed` row counts as written to as well: the provider refusing is not
    evidence that nothing arrived.
    """
    rows = (
        db.query(EmailSend)
        .filter(
            EmailSend.nomination_id == nomination.id,
            EmailSend.purpose == MailPurpose.nomination_proposal,
            EmailSend.state != MailState.queued,
        )
        .all()
    )
    return {row.to_address for row in rows}


def _base_url() -> str:
    """Where the club's screen is served from.

    Read from the same setting the rest of the app's absolute links use, so a
    preview deployment mails a preview link rather than a production one.
    """
    return (settings.public_site_url or "https://ourhike.org").rstrip("/")


def compose(
    club: Club,
    nomination: OrgNomination,
    sources: list[NominationSource],
    contact: NominationContact,
) -> tuple[str, str]:
    """The subject and body one person at the club receives.

    Plain text, and only plain text. An HTML message about somebody's data,
    from a sender they do not know, is the shape of every phishing attempt
    they have been trained to distrust - and there is nothing here that needs
    a typeface.
    """
    base = _base_url()
    read_it = base + PROPOSAL_PATH.format(token=nomination.proposal_token)
    subject = f"A hiker has offered to put {club.name}'s trails on OurHike"

    found = "\n".join(f"  - {source.label}: {source.url}" for source in sources) or (
        "  - nothing yet; whoever proposed this described your trails in their own words"
    )

    body = f"""Hello,

A hiker who walks your trails has proposed adding {club.name}'s published
trail data to OurHike, an open-source offline map for hikers. They are not
affiliated with your organization, and nothing has been published.

We read your public pages and found:

{found}

Your address is on this message because it is published on your own site as a
contact for {contact.role or "your organization"} - {contact.source_page}

WHAT HAPPENS NEXT IS ENTIRELY YOURS.

Three people at your organization have to agree before anything goes live. You
can read exactly what is proposed, line by line, here:

  {read_it}

On that page you can approve it, decline it, or tell us never to ask again -
which we will honour for good, including for any other hiker who tries later.

If you do nothing, nothing happens.

WHAT YOUR ORGANIZATION WOULD GET, AT NO COST.

Your sections drawn from your own data, working offline with no signal. Trail
problems reported by hikers reaching whoever covers that mile. Your workdays
shown to hikers already walking your trails. And your own membership and
giving pages linked from your sections - no money passes through us, and we
take nothing.

OurHike is open source. Your data stays yours, and you can take it and leave
at any point.

- The OurHike maintainers
  {base}
"""
    return subject, body


def ask_the_club(
    db: Session,
    nomination: OrgNomination,
    *,
    provider,
    enabled: bool | None = None,
    allowed: tuple[str, ...] | None = None,
) -> Asked:
    """Write to everybody the hiker kept, once each, and report what happened.

    Does not commit - the caller owns the transaction, the same rule
    `account_deletion.py` and `mail.py` follow.
    """
    enabled = settings.mail_enabled if enabled is None else enabled
    allowed = settings.mail_allowed if allowed is None else allowed

    club = db.query(Club).filter(Club.id == nomination.club_id).one()
    sources = db.query(NominationSource).filter(NominationSource.nomination_id == nomination.id).all()
    contacts = (
        db.query(NominationContact)
        .filter(NominationContact.nomination_id == nomination.id)
        .order_by(NominationContact.created_at)
        .all()
    )
    written = _already_written_to(db, nomination)

    result = Asked()
    for contact in contacts:
        if contact.email in written:
            continue
        subject, body = compose(club, nomination, sources, contact)
        try:
            send(
                db,
                to=contact.email,
                purpose=MailPurpose.nomination_proposal,
                subject=subject,
                body_text=body,
                unsubscribe_url=_base_url() + REFUSE_PATH.format(token=nomination.proposal_token),
                provider=provider,
                enabled=enabled,
                allowed=allowed,
                nomination_id=nomination.id,
            )
        except (MailDisabled, MailSuppressed, MailFailed) as exc:
            result.blocked += 1
            result.reasons.append(exc)
            continue
        result.sent += 1

    # ONLY IF SOMETHING ACTUALLY WENT. A nomination reading `emailed` with
    # nothing sent is the row a maintainer would trust to decide it needs no
    # follow-up.
    if result.sent and nomination.state == NominationState.proposed:
        nomination.state = NominationState.emailed
        nomination.emailed_at = utc_now()
    db.flush()
    return result
