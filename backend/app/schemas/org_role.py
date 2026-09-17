"""Request/response models for roles, invites, the roster and its sync runs.

See ../../../features/ORG_ONBOARDING.md's data model, and #1169 for why an
invite exists at all.

**Rule 4 governs every model in this file: nothing about a named volunteer is
ever published.** So there is no public read of any of these - `can_read_roster`
gates every one - and `publicly_creditable` has no field here at all. It ships
defaulted off with no UI, which is what "there is no consent toggle to build"
means in practice: a field the API cannot set is a field no screen can
accidentally offer.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime
from app.models.org_role import RoleCategory
from app.schemas.common import FiniteFloat, NoteText


class OrgRoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    category: RoleCategory
    reports_to_role_id: str | None
    section_id: str | None
    required: bool
    required_by: str | None
    retired_at: UtcDatetime | None


class OrgRoleCreate(BaseModel):
    name: str
    category: RoleCategory
    reports_to_role_id: str | None = None
    section_id: str | None = None
    required: bool = False
    required_by: str | None = None


class OrgRoleUpdate(BaseModel):
    name: str | None = None
    category: RoleCategory | None = None
    reports_to_role_id: str | None = None
    section_id: str | None = None
    required: bool | None = None
    required_by: str | None = None


class RoleInviteCreate(BaseModel):
    email: str
    role_id: str | None = None
    full_name: str | None = None
    note: NoteText | None = None

    @field_validator("email")
    @classmethod
    def _looks_like_an_address(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("that does not look like an email address")
        return cleaned


class RoleInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    email: str
    role_id: str | None
    full_name: str | None
    invited_at: UtcDatetime
    claimed_at: UtcDatetime | None
    claimed_by: str | None


class RosterEntry(BaseModel):
    """One person on an organization's roster, as the console renders them.

    Two identity shapes in one row, and the distinction is the point: a
    `person_id` means they have signed in and the record is theirs too; a
    row with only `email` is a pending invite, somebody the org knows and
    OurHike has never met. The roster screen shows both, because an org's
    roster is its roster whether or not its people have discovered this app.
    """

    person_id: str | None = None
    email: str | None = None
    display_name: str | None = None
    full_name: str | None = None
    roles: list[str] = []
    sections: list[str] = []
    pending_invite: bool = False


class AssignmentCreate(BaseModel):
    """Putting somebody on a stretch.

    `effective_from` defaults to today rather than being required, because
    the common case is "as of now" and a required date on the common case is
    a form field everybody types the same value into. Backdating stays
    possible, which is what a season that started in March needs.
    """

    person_id: str
    role_id: str | None = None
    section_id: str | None = None
    start_mile: FiniteFloat
    end_mile: FiniteFloat
    effective_from: date | None = None

    @field_validator("start_mile", "end_mile")
    @classmethod
    def _no_negative_miles(cls, value: float) -> float:
        if value < 0:
            raise ValueError("a mile along the trail cannot be negative")
        return value


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    maintainer_id: str
    club_id: str
    role_id: str | None
    section_id: str | None
    start_mile: float
    end_mile: float
    effective_from: date
    effective_to: date | None
    # Set while a supervisor's proposal waits for an admin. Null on an
    # admin's own write and on anything the file loader made.
    proposed_by: str | None = None
    confirmed_by: str | None = None
    confirmed_at: UtcDatetime | None = None


class RosterSyncEntry(BaseModel):
    """One row of an uploaded or fetched roster."""

    email: str
    full_name: str | None = None
    role_name: str | None = None
    section_name: str | None = None
    active: bool = True

    @field_validator("email")
    @classmethod
    def _lowercased(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned:
            raise ValueError("every roster row needs an email address")
        return cleaned


class RosterSyncRequest(BaseModel):
    source: str
    entries: list[RosterSyncEntry]


class RosterSyncResult(BaseModel):
    """What a run did, and what it refused to do.

    `deactivations_held` is the guardrail reporting itself. A run that would
    deactivate more than `DEACTIVATION_HOLD_FRACTION` of an org's live
    assignments applies its additions and holds its deactivations for an
    admin: a changed API field at 4am must not release three hundred roles
    and blank the coverage report before anyone wakes up.

    The held list is returned rather than merely counted, so the screen can
    show an admin exactly who would have been released rather than asking
    them to trust a number.
    """

    run_id: str
    added: int
    updated: int
    deactivated: int
    deactivations_held: int
    held_person_ids: list[str] = []
    held_reason: str | None = None
