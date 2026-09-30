"""What a nomination carries, from the challenge to the club's answer.

See ../../../features/ORG_ONBOARDING.md's "Nominating an organization",
app/models/nomination.py for what is stored, and app/core/urlguard.py for
what may be fetched at all.

**THE READING'S ANSWER IS NOT THE SUBMISSION, and these are two schemas
rather than one for exactly that reason.** `NominateReading` is what comes
back from `POST /assist/nominate`: proposed sources, proposed people, and
nothing written down. `NominationSubmit` is what the hiker sends back after
reviewing it, and only what is in that second object is ever stored. A
person whose address the reading found and the hiker dropped has no row.

Making them one schema would have been shorter and would have quietly turned
"the hiker reviews it" into a display convention - the server would already
hold everything by the time the screen rendered.

**THE HIKER MAY EDIT EVERY FIELD, INCLUDING THE ONES THE READING PROPOSED.**
`proposed_by` on a submitted row says `reading` or `hiker`, and the hiker's
own edits are the hiker's. A club later asking "who said this about us" gets
the true answer per line rather than one answer for the whole submission.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.time import UtcDatetime
from app.schemas.assist import WEBSITE_MAX
from app.schemas.common import EmailAddress

# A club's name, a role, a label on a data source. Generous for a long
# official name ("New York-New Jersey Trail Conference, Ramapo Chapter") and
# bounded because every one of these is rendered on a page.
NAME_MAX = 200
DETAIL_MAX = 600

# Six sources and eight people is past what any club's site has offered in
# the design's own examples (three sources, three people). The cap is not a
# guess at what clubs have; it is a bound on what one submission can write.
MAX_SOURCES = 12
MAX_CONTACTS = 12

ShortName = Annotated[str, Field(max_length=NAME_MAX)]
Detail = Annotated[str, Field(max_length=DETAIL_MAX)]


class ChallengeOut(BaseModel):
    """The work a browser must do before the reading will run.

    Every field is public by construction - see app/core/challenge.py. The
    signature is what makes them unforgeable, not secret.
    """

    nonce: str
    difficulty: int
    expires_at: int
    signature: str


class NominateRead(BaseModel):
    """Read this club's public site. The challenge is not optional.

    Carried in the body rather than a header because it is four fields that
    belong together, and because a header is the thing a proxy strips.
    """

    website: Annotated[str, Field(max_length=WEBSITE_MAX)]
    nonce: str
    difficulty: int
    expires_at: int
    signature: str
    solution: Annotated[str, Field(max_length=64)]


class ProposedSource(BaseModel):
    """One place the reading thinks a club's trail data lives.

    `verdict` is the reading's opinion and is labelled as one everywhere it
    is shown. `not_accepted` is the only value carrying a decision of ours:
    a PDF trail map is a real thing we really found and will not take.
    """

    label: ShortName
    url: Annotated[str, Field(max_length=WEBSITE_MAX)]
    verdict: Literal["usable", "closures", "found", "not_accepted", "unreadable"]
    detail: Detail | None = None


class ProposedContact(BaseModel):
    """One person or role the reading found on the club's own pages.

    `name` is optional and the design's own example is why: "Board president
    · Leadership · president@... · From the Contact page - no name given".
    Absent means nobody published one - never an empty string, never a guess.

    `source_page` is required. Every one of these is a real person's work
    address, and a row that cannot say which of the club's pages it came off
    is a row nobody can answer a question about.
    """

    name: ShortName | None = None
    role: ShortName | None = None
    email: EmailAddress
    source_page: Annotated[str, Field(max_length=WEBSITE_MAX)]


class NominateReading(BaseModel):
    """What we could see, handed to the hiker and stored nowhere.

    `read_at_all` is here so the screen never has to infer it. A reading that
    reached the site and found nothing is a different answer from a reading
    that could not reach the site, and a hiker deciding whether to type the
    sources in by hand needs to know which one they got.
    """

    website: str
    read_at_all: bool
    pages_read: int
    org_name: str | None = None
    summary: str | None = None
    sources: list[ProposedSource] = Field(default_factory=list, max_length=MAX_SOURCES)
    contacts: list[ProposedContact] = Field(default_factory=list, max_length=MAX_CONTACTS)
    membership_url: str | None = None
    donation_url: str | None = None
    # What the reading could see about terms, in the reading's own words. Never
    # rendered as a licence determination: `features/SOURCE_REGISTRY.md` is
    # explicit that a person reads terms before anything of a club's is used,
    # and the nominate page tells the hiker so.
    licence_note: Detail | None = None
    tokens_used: int = 0


class KeptSource(ProposedSource):
    """A source the hiker kept or typed, on the way to being stored."""

    proposed_by: Literal["reading", "hiker"] = "reading"


class KeptContact(ProposedContact):
    """A person the hiker kept or typed, on the way to being stored."""

    proposed_by: Literal["reading", "hiker"] = "reading"


class NominationSubmit(BaseModel):
    """The whole of what a nomination writes down.

    Deliberately not "the reading, plus edits". The hiker sends the final
    list; nothing on the server is merged into it; and a contact absent here
    was never stored, whatever the reading proposed.
    """

    website: Annotated[str, Field(max_length=WEBSITE_MAX)]
    org_name: ShortName
    region: ShortName | None = None
    sources: list[KeptSource] = Field(default_factory=list, max_length=MAX_SOURCES)
    contacts: list[KeptContact] = Field(default_factory=list, max_length=MAX_CONTACTS)

    @field_validator("contacts")
    @classmethod
    def _somebody_has_to_be_asked(cls, value: list[KeptContact]) -> list[KeptContact]:
        """A nomination with nobody to ask cannot go anywhere.

        Three approvals is the rule for an org that signs itself up and the
        design applies it here unchanged. Fewer than one address means the
        club can never be asked at all, and a row that can only ever sit
        there is worse than a refusal at the door.
        """
        if not value:
            raise ValueError("We need at least one address at the club, or nobody there can be asked.")
        addresses = [contact.email.lower() for contact in value]
        if len(set(addresses)) != len(addresses):
            raise ValueError("Two of those contacts are the same address.")
        return value


class NominationOut(BaseModel):
    """A nomination as its own hiker sees it afterwards."""

    id: str
    club_slug: str
    website: str
    state: Literal["proposed", "emailed", "accepted", "declined", "withdrawn"]
    created_at: UtcDatetime
    emailed_at: UtcDatetime | None = None
    decided_at: UtcDatetime | None = None
    contacts_asked: int = 0
    contacts_answered: int = 0


class ProposalContactOut(BaseModel):
    """One of the people asked, as the club's own screen shows them.

    The address is here because the club is looking at their own colleagues
    and the screen exists to let them say "that is the wrong person". It is
    not in `NominationOut`: the nominating hiker never sees who was asked,
    and never learns who declined.
    """

    name: str | None = None
    role: str | None = None
    email: EmailAddress
    source_page: str
    responded: bool = False


class ProposalOut(BaseModel):
    """What somebody at the club sees when they open the link we mailed them.

    Unauthenticated, addressed by token, and deliberately complete: a person
    asked to approve publishing their organization's data should not have to
    make an account to read what is being proposed.
    """

    org_name: str
    website: str
    proposed_by_display: str
    proposed_at: UtcDatetime
    sources: list[ProposedSource] = Field(default_factory=list)
    contacts: list[ProposalContactOut] = Field(default_factory=list)
    approvals_required: int
    approvals_so_far: int
    state: Literal["proposed", "emailed", "accepted", "declined", "withdrawn"]


class ProposalDecision(BaseModel):
    """A club's answer, and the one that closes the door.

    `never_ask_again` is not a nicer word for declining. Declining says no to
    this nomination; `never_ask_again` writes a `nomination_refusals` row
    keyed by the club's domain, and the next hiker who tries is stopped
    before anybody there is emailed a second time.
    """

    approve: bool
    never_ask_again: bool = False
    note: Detail | None = None
