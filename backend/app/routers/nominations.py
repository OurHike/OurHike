"""`/assist/nominate` and `/nominations` - a hiker offering somebody else's trails.

See ../../../features/ORG_ONBOARDING.md's "Nominating an organization". Every
route in the flow lives here rather than being split across `assist.py` and
`clubs.py`, because it is one story with one set of rules and CONTRIBUTING.md's
one-home rule applies to routes as much as to documents.

**THE PANEL IS NOT PUBLIC ANY MORE, and that is the largest change in this
file.** It used to take a website from anybody on the internet, send it to a
model with no tools, and render the reply under "WHAT WE COULD SEE ON THEIR
SITE". Nothing had been seen. Now: signed in, a proof of work, a budget, a
guard that decides what may be opened, a fetch, and a reading checked back
against the pages it claims to come from.

**THREE BOUNDS, EACH DOING SOMETHING THE OTHERS DO NOT.** Signing in bounds
who can ask. `app/core/challenge.py` bounds how fast one account can ask.
`app/core/assist.py`'s budget bounds what it all costs. Removing any one of
them leaves a hole the other two do not cover, which is why the maintainer
asked for all three on 2026-09-17.

**THE CLUB'S OWN SCREEN IS ADDRESSED BY TOKEN AND NEEDS NO ACCOUNT.** Nobody
at the club has one, and requiring them to make one in order to answer "is
this yours?" would be a sign-up wall in front of a question we asked them.
The token is long, random and expiring, because a link mailed to three people
is a link that gets forwarded, pasted into a helpdesk ticket, and indexed.

**ONE REFUSAL STOPS IT; THREE APPROVALS ARE NEEDED TO PROCEED.** Deliberately
asymmetric, and the same asymmetry the rest of this project uses on anything
that reaches a hiker: a club that does not want this has said so once and
should not have to say it three times, while publishing their data is a thing
we make hard.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.assist import (
    AssistBudgetSpent,
    AssistFailed,
    AssistUnavailable,
    ask,
)
from app.core.auth import get_current_user
from app.core.challenge import Challenge, ChallengeRefused, issue, verify
from app.core.mail import ses_client
from app.core.nominate import ReadingFailed, reading_from
from app.core.nomination_mail import ask_the_club
from app.core.sitefetch import (
    FetchRefused,
    peer_from_response,
    peer_unchecked,
    read_site,
    reader,
)
from app.core.time import utc_now
from app.core.urlguard import UrlRefused
from app.db.session import get_db
from app.models.club import Club, OrgState
from app.models.nomination import (
    ChallengeSpend,
    NominationContact,
    NominationRefusal,
    NominationSource,
    NominationState,
    OrgNomination,
    ProposedBy,
    SourceVerdict,
)
from app.models.profile import Profile
from app.schemas.nomination import (
    ChallengeOut,
    NominateRead,
    NominateReading,
    NominationOut,
    NominationSubmit,
    ProposalContactOut,
    ProposalDecision,
    ProposalOut,
    ProposedSource,
)

router = APIRouter(tags=["nominations"])

# Three, as the design says and as an organization signing itself up already
# needs. A club with fewer than three published addresses cannot reach this on
# its own and waits for a person, which is the honest outcome rather than a
# threshold that quietly lowers itself.
APPROVALS_REQUIRED = 3

# Long enough for three people at a volunteer organization to find the message,
# read it, and talk to each other. Short enough that a forwarded link does not
# stay live for a year.
TOKEN_DAYS = 45


def _challenge_secret() -> str:
    if not settings.nominate_challenge_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nominating an organization is not switched on for this deployment.",
        )
    return settings.nominate_challenge_secret


def _spender(db: Session):
    """Spend a nonce, or report that somebody already did.

    The uniqueness is the primary key's rather than a read-then-write, because
    two requests presenting the same solved challenge at the same moment is
    exactly the case a check-then-insert loses.
    """

    def spend(nonce: str) -> bool:
        row = ChallengeSpend(nonce=nonce, expires_at=utc_now() + timedelta(hours=1))
        db.add(row)
        try:
            # COMMITTED HERE AND NOT AT THE END OF THE REQUEST. A flush alone
            # is rolled back with everything else when the route raises - and
            # this route raises on every refusal downstream of it, so a
            # rejected fetch would hand the nonce back and the challenge would
            # be good again. The work is spent the moment it is accepted; a
            # hiker whose fetch then fails asks for a new challenge, which is
            # the cheap half of the trade.
            db.commit()
        except IntegrityError:
            db.rollback()
            return False
        return True

    return spend


@router.get("/assist/nominate/challenge", response_model=ChallengeOut)
def nominate_challenge(current_user: Profile = Depends(get_current_user)) -> ChallengeOut:
    """The work this hiker's browser must do before we will read a website.

    Bound to them: `app/core/challenge.py` puts the subject inside the
    signature, so a challenge solved once cannot be handed to somebody else.
    """
    challenge = issue(
        current_user.id,
        secret=_challenge_secret(),
        now=int(utc_now().timestamp()),
        difficulty=settings.nominate_challenge_difficulty,
    )
    return ChallengeOut(**challenge.__dict__)


@router.post("/assist/nominate", response_model=NominateReading)
def nominate_read(
    payload: NominateRead,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NominateReading:
    """Read a club's public site, and report only what was on it.

    Every refusal here has its own status because each is a different thing to
    tell the person on the other end: 400 is "that is not an address we will
    open", 409 is "your challenge is stale, ask for another", 429 is "the
    budget is spent", 502 is "their site would not answer".
    """
    try:
        verify(
            Challenge(
                nonce=payload.nonce,
                difficulty=payload.difficulty,
                expires_at=payload.expires_at,
                signature=payload.signature,
            ),
            payload.solution,
            subject=current_user.id,
            secret=_challenge_secret(),
            spend=_spender(db),
            now=int(utc_now().timestamp()),
        )
    except ChallengeRefused as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    # THE BUDGET COUNTS THIS HIKER, NOT THEIR ADDRESS. When the panel was
    # public there was nothing else to count by; now there is, and it is
    # better in both directions - an address counts a whole office together
    # and counts one person on two networks twice. It also means no address is
    # stored at all, hashed or otherwise, so this endpoint stops being a
    # record of who looked up which organization.
    def asker(prompt: str, system: str) -> tuple[str, int]:
        result = ask(
            db,
            panel="nominate",
            system=system,
            prompt=prompt,
            club=None,
            counted_as=f"hiker:{current_user.id}",
        )
        return result.text, result.input_tokens + result.output_tokens

    try:
        # A client per request rather than one shared for the process. The
        # handshake costs a moment and the alternative is a cookie jar and a
        # connection pool shared across every organization anybody nominates -
        # see this module's note on what must not leave with the request.
        with reader() as client:
            pages = read_site(
                payload.website,
                client=client,
                # OFF means REFUSE, not "skip the check" - `peer_unchecked`
                # reports the peer as unknown and `read_page` treats unknown as
                # a failure. A deployment behind an egress proxy has to turn the
                # whole reading off rather than run it unverified.
                read_peer=peer_from_response if settings.site_fetch_require_peer_match else peer_unchecked,
            )
    except UrlRefused as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FetchRefused as exc:
        # NOT a 502 dressed up as an empty reading. A hiker who is told
        # nothing was found will type the sources in by hand; one shown an
        # empty result under "what we could see" reads it as "this club
        # publishes nothing", which is a claim about somebody's organization.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    try:
        return reading_from(payload.website, pages, ask=asker)
    except AssistUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AssistBudgetSpent as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except (AssistFailed, ReadingFailed) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


def _domain_of(website: str) -> str:
    from urllib.parse import urlsplit

    raw = website if "://" in website else f"https://{website}"
    return (urlsplit(raw).hostname or "").lower().removeprefix("www.")


def _slug_for(db: Session, name: str, domain: str) -> str:
    """A readable id nobody else has.

    The domain is the tiebreak rather than a counter, because two clubs with
    the same name are two different domains and a `-2` suffix tells a reader
    nothing about which is which.
    """
    import re

    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "organization"
    if db.query(Club).filter(Club.slug == base).first() is None:
        return base
    stem = domain.split(".")[0] if domain else secrets.token_hex(3)
    candidate = f"{base}-{stem}"
    if db.query(Club).filter(Club.slug == candidate).first() is None:
        return candidate
    return f"{base}-{secrets.token_hex(3)}"


@router.post("/clubs/nominations", response_model=NominationOut, status_code=status.HTTP_201_CREATED)
def submit_nomination(
    payload: NominationSubmit,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NominationOut:
    """Write down what the hiker kept, and nothing the hiker dropped.

    **This is the only place a proposed contact becomes a row.** The reading
    handed the browser a list and stored none of it; what arrives here is the
    hiker's final answer, and a person whose address the reading found and the
    hiker removed was never written down at all. That is the maintainer's
    2026-09-17 condition implemented rather than displayed.
    """
    domain = _domain_of(payload.website)
    if domain and db.query(NominationRefusal).filter(NominationRefusal.domain == domain).first():
        # Before anything is written and before anybody there is emailed a
        # second time. A refusal is a promise about every future hiker.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("That organization has asked us not to take proposals about their data. Thank you for thinking of them."),
        )

    club = Club(
        name=payload.org_name,
        slug=_slug_for(db, payload.org_name, domain),
        website=payload.website,
        region=payload.region,
        domain=domain or None,
        state=OrgState.unclaimed,
        created_by=current_user.id,
    )
    db.add(club)
    db.flush()

    nomination = OrgNomination(
        club_id=club.id,
        nominated_by=current_user.id,
        website=payload.website,
        state=NominationState.proposed,
        proposal_token=secrets.token_urlsafe(32),
        token_expires_at=utc_now() + timedelta(days=TOKEN_DAYS),
    )
    db.add(nomination)
    db.flush()

    for source in payload.sources:
        db.add(
            NominationSource(
                nomination_id=nomination.id,
                label=source.label,
                url=source.url,
                verdict=SourceVerdict(source.verdict),
                detail=source.detail,
                proposed_by=ProposedBy(source.proposed_by),
            )
        )
    for contact in payload.contacts:
        db.add(
            NominationContact(
                nomination_id=nomination.id,
                name=contact.name,
                role=contact.role,
                email=str(contact.email).lower(),
                source_page=contact.source_page,
                proposed_by=ProposedBy(contact.proposed_by),
            )
        )
    # ASK THEM NOW, in the same transaction that wrote the nomination down.
    # Deliberately not a queue: a queue is a thing that stops being drained,
    # and #1123 is this repository's standing issue about exactly that shape
    # of dropped handoff. `ask_the_club` reports what happened rather than
    # raising, and leaves the nomination at `proposed` when nothing went - so
    # a deployment with mail off (every preview, and the default) records a
    # nomination a maintainer can see and makes no claim to have asked
    # anybody.
    ask_the_club(db, nomination, provider=ses_client())
    db.commit()
    return _nomination_out(db, nomination, club)


def _nomination_out(db: Session, nomination: OrgNomination, club: Club) -> NominationOut:
    contacts = db.query(NominationContact).filter(NominationContact.nomination_id == nomination.id).all()
    return NominationOut(
        id=nomination.id,
        club_slug=club.slug,
        website=nomination.website,
        state=nomination.state.value,
        created_at=nomination.created_at,
        emailed_at=nomination.emailed_at,
        decided_at=nomination.decided_at,
        contacts_asked=len(contacts),
        contacts_answered=sum(1 for c in contacts if c.responded_at is not None),
    )


def _by_token(db: Session, token: str) -> tuple[OrgNomination, Club]:
    """The nomination this link addresses, or a 404 that says nothing else.

    One message for expired, withdrawn and never-existed alike: this endpoint
    takes a secret from anybody who has the URL, and a distinguishing error is
    an oracle for guessing tokens.
    """
    nomination = db.query(OrgNomination).filter(OrgNomination.proposal_token == token).first() if token else None
    if nomination is None or nomination.token_expires_at <= utc_now() or nomination.state == NominationState.withdrawn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That link has expired or is not one of ours.",
        )
    club = db.query(Club).filter(Club.id == nomination.club_id).first()
    if club is None:  # pragma: no cover - a nomination always has its club
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That link is not one of ours.")
    return nomination, club


@router.get("/nominations/{token}", response_model=ProposalOut)
def read_proposal(token: str, db: Session = Depends(get_db)) -> ProposalOut:
    """What somebody at the club sees when they open the link we mailed them.

    Complete on purpose. A person asked to approve publishing their
    organization's data should be able to read exactly what is proposed
    without making an account first.
    """
    nomination, club = _by_token(db, token)
    sources = db.query(NominationSource).filter(NominationSource.nomination_id == nomination.id).all()
    contacts = db.query(NominationContact).filter(NominationContact.nomination_id == nomination.id).all()
    return ProposalOut(
        org_name=club.name,
        website=nomination.website,
        # THE HIKER IS DESCRIBED, NOT NAMED. The design's own screen says "Sam
        # Ortiz - a hiker from Durham"; what it never does is hand the club a
        # way to contact them, and what the other direction never does is tell
        # the hiker who declined.
        proposed_by_display="A hiker on OurHike",
        proposed_at=nomination.created_at,
        sources=[
            ProposedSource(
                label=source.label,
                url=source.url,
                verdict=source.verdict.value,
                detail=source.detail,
            )
            for source in sources
        ],
        contacts=[
            ProposalContactOut(
                name=contact.name,
                role=contact.role,
                email=contact.email,
                source_page=contact.source_page,
                responded=contact.responded_at is not None,
            )
            for contact in contacts
        ],
        approvals_required=APPROVALS_REQUIRED,
        approvals_so_far=sum(1 for c in contacts if c.approved is True),
        state=nomination.state.value,
    )


@router.post("/nominations/{token}/decision", response_model=ProposalOut)
def decide_proposal(
    token: str,
    payload: ProposalDecision,
    db: Session = Depends(get_db),
) -> ProposalOut:
    """One of the people we asked, answering.

    **ONE REFUSAL STOPS IT AND THREE APPROVALS ARE NEEDED TO PROCEED.** The
    asymmetry is the same one this project applies to anything that reaches a
    hiker: a club that does not want this has said so once and should not have
    to say it three times, while publishing their data is a thing we make hard.

    `never_ask_again` is not a stronger word for declining. Declining answers
    this proposal; `never_ask_again` writes a `nomination_refusals` row keyed
    by the club's own domain, and the next hiker to try is stopped at
    `POST /clubs/nominations` before anybody there is written to a second time.
    """
    nomination, club = _by_token(db, token)

    # LOCKED BEFORE THE STATE IS READ, because the link goes to three people
    # and nothing stops two of them answering in the same moment. Without the
    # lock both read `proposed`, both pick the same first un-answered contact,
    # and the last commit wins - so two approvals record as one, and worse, a
    # REFUSAL racing an approval is overwritten. "One refusal ends it" is the
    # asymmetry this whole endpoint is built on, and it was the thing the race
    # could silently take away.
    #
    # `populate_existing` because `_by_token` has already put this row in the
    # session's identity map: without it the locked SELECT would refresh the
    # database row and leave the stale in-memory object for the check below to
    # read. The second caller now waits, then sees the first's committed state
    # and answers 409.
    #
    # The first `with_for_update` in `backend/app/`. It is here and not in
    # `_by_token` because reading a proposal is a GET that should not queue
    # behind anybody.
    nomination = db.query(OrgNomination).filter(OrgNomination.id == nomination.id).populate_existing().with_for_update().one()

    if nomination.state in (NominationState.accepted, NominationState.declined):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somebody at your organization has already answered this one.",
        )

    # WHICH OF THEM IS ANSWERING IS NOT ASKED, and cannot be. The link goes to
    # three addresses and arrives in three inboxes that forward to each other;
    # asking the opener to identify themselves from a list of their own
    # colleagues is a question with an obvious wrong answer available. So an
    # approval counts the first contact who has not answered, and the
    # threshold means three separate openings of the link rather than three
    # provable people. @unvalidated as a control: it is strictly weaker than
    # per-recipient tokens, which is what would settle it, and it is not
    # weaker than what an organization signing itself up does today.
    pending = (
        db.query(NominationContact)
        .filter(
            NominationContact.nomination_id == nomination.id,
            NominationContact.responded_at.is_(None),
        )
        .order_by(NominationContact.created_at)
        .first()
    )
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Everybody we asked has already answered this one.",
        )

    now = utc_now()
    pending.responded_at = now
    pending.approved = bool(payload.approve)

    if not payload.approve:
        nomination.state = NominationState.declined
        nomination.decided_at = now
        nomination.decided_note = payload.note
        if payload.never_ask_again and club.domain:
            # `nomination_refusals.domain` is unique, and the gate that stops
            # a second nomination is checked when one is submitted rather
            # than when one is decided - so two nominations for one club can
            # both be live and both be declined this way. Inserting blind
            # raised IntegrityError on the second, and the rollback took the
            # decline with it: the club had said no and the row still read
            # `proposed`. Already-refused is the state this asks for, so
            # finding it there is success, not a collision.
            already = db.query(NominationRefusal).filter(NominationRefusal.domain == club.domain).one_or_none()
            if already is None:
                db.add(
                    NominationRefusal(
                        domain=club.domain,
                        note=payload.note,
                    )
                )
            elif payload.note and not already.note:
                # The first refusal said no without saying why and this one
                # explains. Keep the earlier date - that is when they told
                # us - and take the words, because a reason nobody recorded
                # is the thing a person reading this later actually needs.
                already.note = payload.note
        # The org row itself goes. It exists only because a hiker offered, and
        # a club that said no should not be left as an `unclaimed` row with
        # their name on it in somebody's admin list.
        club.state = OrgState.deleted
    else:
        # Flushed first: this session does not autoflush, so the approval just
        # assigned above is invisible to a query that does not ask for it -
        # which made the third approval count two and leave the nomination
        # sitting at `proposed` forever.
        db.flush()
        approvals = (
            db.query(NominationContact)
            .filter(
                NominationContact.nomination_id == nomination.id,
                NominationContact.approved.is_(True),
            )
            .count()
        )
        if approvals >= APPROVALS_REQUIRED:
            nomination.state = NominationState.accepted
            nomination.decided_at = now

    db.commit()
    return read_proposal(token, db=db)
