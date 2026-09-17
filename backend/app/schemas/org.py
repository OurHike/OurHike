"""Request/response models for `/clubs` - the organization itself.

`Org` is the word every screen uses and `clubs` is the table's name; see
../../../features/ORG_ONBOARDING.md's conflict 2 for why the route did not
get renamed to match the UI. The schema class names follow the UI, because a
reader of a FastAPI response model is reading the API's vocabulary rather
than the database's.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime
from app.models.club import OrgState, VerifiedBy
from app.schemas.common import NoteText

# A slug is lowercase alphanumerics and single hyphens, 3 to 64 characters.
#
# It has to survive being a path segment, a `data-org` attribute in somebody
# else's HTML and a directory name in a pull request, so the character set is
# the intersection of what all three take without escaping rather than the
# most permissive any one of them allows.
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_MIN = 3
SLUG_MAX = 64

# Slugs nobody may register, because each already means something else under
# `/org/`. Kept short and checked rather than guessed at: these are the path
# segments this design actually uses.
RESERVED_SLUGS = frozenset(
    {"new", "claim", "nominate", "nominations", "demo", "setup", "volunteers", "admins", "admin", "api", "org"}
)


def slugify(name: str) -> str:
    """A candidate slug for `name` - the same shape the migration backfills.

    Not authoritative: an org picks its own at registration, and this only
    proposes one so the form can be pre-filled. Kept beside the validator so
    the two cannot drift into proposing something the other refuses.
    """
    candidate = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return candidate[:SLUG_MAX].rstrip("-")


class OrgAdminOut(BaseModel):
    """One admin's seat, as the approval screen renders it.

    Carries `approved_at`/`declined_at` rather than a single status word,
    because a decline is reversible and a status enum would need a value for
    "declined, then approved" that means nothing to a reader. The two
    timestamps say what happened in the order it happened.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    person_id: str
    title: str | None
    is_codeowner: bool
    invited_at: UtcDatetime
    approved_at: UtcDatetime | None
    declined_at: UtcDatetime | None
    decline_reason: str | None


class OrgOut(BaseModel):
    """An organization as the console and the public page both read it.

    One model rather than a public/private split, because there is nothing
    here a hiker may not see: the roster, the hours and the unpublished
    registry are all other resources. What an org publishes about itself is
    public by construction - that is what registering is.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str | None
    name: str
    region: str | None
    domain: str | None
    website: str | None
    verified_by: VerifiedBy | None
    state: OrgState
    membership_url: str | None
    donation_url: str | None
    created_at: UtcDatetime
    admins: list[OrgAdminOut] = []


class OrgAdminInvite(BaseModel):
    """One of the three people named at registration.

    Email rather than a person id, because at registration none of them have
    necessarily signed in - #1169's problem 3, and the reason `RoleInvite`
    exists. The seat is created when they first sign in.
    """

    email: str
    title: str | None = None

    @field_validator("email")
    @classmethod
    def _looks_like_an_address(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("that does not look like an email address")
        return cleaned


class OrgCreate(BaseModel):
    """Registering. One admin fills this in; three approve before anything publishes."""

    name: str
    slug: str
    domain: str
    website: str | None = None
    region: str | None = None
    membership_url: str | None = None
    donation_url: str | None = None
    admins: list[OrgAdminInvite] = []

    @field_validator("slug")
    @classmethod
    def _usable_as_an_address(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not SLUG_MIN <= len(cleaned) <= SLUG_MAX:
            raise ValueError(f"a slug is {SLUG_MIN} to {SLUG_MAX} characters")
        if not SLUG_PATTERN.match(cleaned):
            raise ValueError("a slug is lowercase letters, digits and single hyphens")
        if cleaned in RESERVED_SLUGS:
            raise ValueError(f"{cleaned!r} is reserved - it already means something under /org/")
        return cleaned

    @field_validator("domain")
    @classmethod
    def _a_bare_domain(cls, value: str) -> str:
        # A bare hostname, because it is compared against the part of an
        # email address after the `@`. Accepting "https://ramapotrails.org/"
        # here and comparing it to "ramapotrails.org" would fail the
        # domain check for every admin and give no reason why.
        cleaned = value.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
        if "." not in cleaned or " " in cleaned:
            raise ValueError("give the bare domain, e.g. ramapotrails.org")
        return cleaned


class OrgSettingsUpdate(BaseModel):
    """What an admin may change afterwards, and what they may not.

    `slug` is absent on purpose. It is in every route, every embed snippet an
    org has already pasted onto their own website, and every pull-request
    path. Changing it silently breaks all three, so it is a conversation with
    a maintainer rather than a form field.
    """

    name: str | None = None
    region: str | None = None
    website: str | None = None
    membership_url: str | None = None
    donation_url: str | None = None


class OrgClaimRequest(BaseModel):
    """Claiming an org that has live trails and no admins.

    An email at the org's domain is the whole check. The address is not sent
    here: it comes from the caller's verified token, because an address the
    caller typed proves nothing.
    """

    title: str | None = None
    note: NoteText | None = None


class OrgDeclineRequest(BaseModel):
    reason: NoteText | None = None


class OrgNomination(BaseModel):
    """A hiker submitting an org's trails on its behalf.

    Deliberately thin. The hiker is not claiming to speak for the
    organization and must not be asked to - they know their local club has
    trails and roughly where to find them, and that is the whole of what this
    collects. A maintainer reads it and does the rest.
    """

    name: str
    website: str | None = None
    region: str | None = None
    data_url: str | None = None
    note: NoteText | None = None
