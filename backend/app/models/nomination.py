"""A hiker putting somebody else's organization on the map, and its aftermath.

See ../../../features/ORG_ONBOARDING.md's "Nominating an organization" and
the design handoff's nominate screen. A hiker who is not affiliated with a
club gives us its website; we read the public site; the hiker reviews what
we found; and three people at that club decide.

**NOTHING A MODEL PROPOSED IS STORED UNTIL THE HIKER KEEPS IT.** That is the
maintainer's 2026-09-17 condition on harvesting contacts, implemented
literally rather than as a display convention. `POST /assist/nominate`
returns proposed sources and proposed people to the browser and writes
nothing; only what comes back on the submit lands in `nomination_sources`
and `nomination_contacts`. A person whose address the reading found and the
hiker dropped was never written down, so there is no row to leak, no row to
export, and nothing to delete later on their behalf.

**`nomination_contacts` HOLDS NAMED PEOPLE'S WORK ADDRESSES, AND THAT IS THE
POINT OF SAYING SO HERE.** Every one of them was published by the
organization itself on a page anybody can read - that is the only reason
this is defensible at all - but a scattered publication and a database are
not the same object, and a reader of this file should not have to discover
the difference. `source_page` is mandatory for exactly that reason: every
row can say which of the club's own pages it came off, so a person asking
"where did you get this" gets an answer rather than a shrug.

**A REFUSAL OUTLIVES EVERYTHING ELSE HERE.** `nomination_refusals` is not a
column on the nomination, because the nomination can be deleted and the
refusal must not be: "No thank you" on the club-facing screen means we do
not ask again, ever, and a promise that a later cleanup job can erase is not
a promise. It is keyed by domain, so a second hiker nominating the same club
next year is stopped before anybody at that club is emailed.
"""

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint

from app.core.time import utc_now
from app.db.base import Base


class NominationState(str, enum.Enum):
    """Where a nomination sits between a hiker's idea and a club's answer.

    `proposed` is a nomination the hiker submitted and nobody at the club has
    been told about yet - the state everything starts in, and the one a
    maintainer looks at. `withdrawn` is the hiker changing their mind, which
    is theirs to do right up until the club has been asked.
    """

    proposed = "proposed"
    emailed = "emailed"
    accepted = "accepted"
    declined = "declined"
    withdrawn = "withdrawn"


class SourceVerdict(str, enum.Enum):
    """What the reading made of one thing it found on a club's site.

    `not_accepted` is the one carrying a decision rather than an observation:
    a PDF trail map is a real thing we really found and will not take,
    because a PDF cannot be re-read and is stale the day it is uploaded. The
    nominate page says so to the hiker in those words.
    """

    usable = "usable"
    closures = "closures"
    found = "found"
    not_accepted = "not_accepted"
    unreadable = "unreadable"


class ProposedBy(str, enum.Enum):
    """Who put this row forward.

    Kept per row rather than per nomination because the screen mixes them:
    the reading proposes, the hiker adds and removes, and a club later asking
    "who said this about us" deserves the true answer for each line.
    """

    reading = "reading"
    hiker = "hiker"


class OrgNomination(Base):
    """One hiker offering one organization's trails, on its behalf.

    `club_id` points at the `clubs` row created in the `unclaimed` state, so
    everything downstream - the registry, the proposal screen, the eventual
    claim - works on the same object an organization that signed itself up
    would have. The nomination is the story of how that row got there.
    """

    __tablename__ = "org_nominations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)
    # The hiker who offered. Never an admin of anything here by doing so -
    # the design says it outright and so does the page: "You are a proposer,
    # not an admin."
    nominated_by = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
    website = Column(String, nullable=False)
    state = Column(Enum(NominationState, native_enum=False, length=20), nullable=False, default=NominationState.proposed)

    # THE TOKEN IS THE CLUB'S ONLY WAY IN, because nobody at the club has an
    # account yet and requiring one to answer "is this yours?" would be a
    # sign-up wall in front of a question we asked them. Long, random, and
    # expiring: a link mailed to three people is a link that will end up
    # forwarded, pasted into a ticket, and indexed if the club's helpdesk is
    # public.
    proposal_token = Column(String, nullable=False, unique=True, index=True)
    token_expires_at = Column(DateTime, nullable=False)

    # What the reading cost, kept so the first real nominations can answer
    # what this feature actually costs to run. Not the prompt, not the answer
    # - the same rule `assist_usage` follows.
    pages_read = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    emailed_at = Column(DateTime, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    # What the club said when they declined, if they chose to say anything.
    # Never shown to the nominating hiker: the design is explicit that "Sam is
    # not told who declined."
    decided_note = Column(Text, nullable=True)


class NominationSource(Base):
    """One place a club's trail data lives, as proposed and as reviewed."""

    __tablename__ = "nomination_sources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nomination_id = Column(String, ForeignKey("org_nominations.id"), nullable=False, index=True)
    label = Column(String, nullable=False)
    url = Column(String, nullable=False)
    verdict = Column(Enum(SourceVerdict, native_enum=False, length=20), nullable=False)
    # Free text from the reading - "214 line features, BLZ_COLOR present" -
    # shown to the club as what we think we saw, never as a fact about them.
    detail = Column(Text, nullable=True)
    proposed_by = Column(Enum(ProposedBy, native_enum=False, length=10), nullable=False, default=ProposedBy.reading)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    __table_args__ = (UniqueConstraint("nomination_id", "url", name="uq_nomination_source_url"),)


class NominationContact(Base):
    """One person or role at the club, as published by the club.

    `name` is nullable and the design's own example is why: "Board president
    · Leadership · president@... · From the Contact page - no name given".
    An absent name means nobody claimed one, never an empty string and never
    a guess - the same rule the shelter capacity export follows.
    """

    __tablename__ = "nomination_contacts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nomination_id = Column(String, ForeignKey("org_nominations.id"), nullable=False, index=True)
    name = Column(String, nullable=True)
    role = Column(String, nullable=True)
    email = Column(String, nullable=False)
    # Which of the club's own pages this came off. NOT NULL deliberately:
    # every row must be able to answer "where did you get this".
    source_page = Column(String, nullable=False)
    proposed_by = Column(Enum(ProposedBy, native_enum=False, length=10), nullable=False, default=ProposedBy.reading)
    # Set when this contact answers, so the sign-off can count three people
    # rather than three clicks from one inbox.
    responded_at = Column(DateTime, nullable=True)
    approved = Column(Boolean, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    __table_args__ = (UniqueConstraint("nomination_id", "email", name="uq_nomination_contact_email"),)


class NominationRefusal(Base):
    """An organization that has said not to ask again, kept forever.

    Deliberately not a column on the nomination: the nomination can be
    deleted and this cannot, because "No thank you" is a promise about every
    future hiker and not about this one. Checked before a nomination is
    accepted at all, so the second hiker to try is told no before anybody at
    the club is emailed a second time.
    """

    __tablename__ = "nomination_refusals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # The club's own domain, lowercased. A domain rather than a club id
    # because the refusing club may never have had a row of its own, and a
    # second nomination would otherwise create a fresh one and ask again.
    domain = Column(String, nullable=False, unique=True, index=True)
    refused_at = Column(DateTime, nullable=False, default=utc_now)
    note = Column(Text, nullable=True)


class ChallengeSpend(Base):
    """One proof-of-work nonce, spent.

    The only thing `app/core/challenge.py` needs stored. Without it a solved
    challenge is a token good forever - one solve for somebody running this
    in bulk and then nothing, while still costing every honest hiker one.

    Rows are disposable once `expires_at` has passed: a nonce that can no
    longer be presented cannot be replayed, so this table is a fixed size
    rather than a growing log.
    """

    __tablename__ = "challenge_spends"

    nonce = Column(String, primary_key=True)
    spent_at = Column(DateTime, nullable=False, default=utc_now)
    expires_at = Column(DateTime, nullable=False, index=True)
