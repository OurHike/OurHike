"""Request and response bodies. Every string a person types is bounded and
stripped of control characters here, so nothing downstream has to remember to."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from steward_api import limits


def _no_control_characters(value: str) -> str:
    if any(ord(ch) < 32 or 0x7F <= ord(ch) < 0xA0 for ch in value):
        raise ValueError("must not contain control characters")
    return value


def _text(max_length: int) -> type[str]:
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
        AfterValidator(_no_control_characters),
    ]


ListName = _text(limits.LIST_NAME_MAX)
DisplayName = _text(limits.DISPLAY_NAME_MAX)
Note = _text(limits.NOTE_MAX)
Club = _text(limits.CLUB_MAX)
RimsId = Annotated[str, StringConstraints(pattern=limits.RIMS_ID_PATTERN)]
Weight = Annotated[int, Field(ge=0, le=limits.WEIGHT_MAX)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Me(BaseModel):
    display_name: str | None


class MeUpdate(Strict):
    #: None clears it.
    display_name: DisplayName | None


class ListCreate(Strict):
    name: ListName
    rims_ids: list[RimsId] = Field(default_factory=list, max_length=limits.ITEMS_PER_LIST)


class ListRename(Strict):
    name: ListName


class ListSummary(BaseModel):
    id: uuid.UUID
    name: str
    item_count: int
    shared: bool
    created_at: datetime
    updated_at: datetime


class ListDetail(ListSummary):
    rims_ids: list[str]


class ShareLink(BaseModel):
    #: Shown once. Only its hash is kept, so a lost token is replaced, not recovered.
    token: str


class SharedLookup(Strict):
    token: Annotated[str, StringConstraints(min_length=16, max_length=128)]


class SharedList(BaseModel):
    name: str
    owner: str | None
    rims_ids: list[str]
    updated_at: datetime


class WeightValues(Strict):
    deficit: Weight
    water: Weight
    trail: Weight
    cluster: Weight
    restricted: Weight


class WeightsChange(WeightValues):
    club: Club
    note: Note | None = None


class WeightsRestore(Strict):
    note: Note | None = None


class WeightsEntry(BaseModel):
    id: int
    deficit: int
    water: int
    trail: int
    cluster: int
    restricted: int
    note: str | None
    restored_from: int | None
    #: The display name of whoever made the change, or None if they set none.
    changed_by: str | None
    by_you: bool
    changed_at: datetime


class ClubWeightsView(BaseModel):
    club: str
    #: The weights in force: the newest entry's, or the defaults if there is none.
    current: dict[str, int]
    defaults: dict[str, int]
    #: Newest first, at most HISTORY_LIMIT entries.
    history: list[WeightsEntry]


# --- Claims (phase 3, #1910) ------------------------------------------------------

Step = _text(limits.STEP_MAX)
NotesText = _text(limits.NOTES_MAX)
ReviewNote = _text(limits.REVIEW_NOTE_MAX)


class ClaimCreate(Strict):
    #: One site, or a site and the rest of its cluster ("Claim all 3").
    rims_ids: list[RimsId] = Field(min_length=1, max_length=limits.SITES_PER_CLAIM_REQUEST)


class ClaimSummary(BaseModel):
    id: uuid.UUID
    rims_id: str
    state: str
    claimed_at: datetime
    due_at: datetime
    submitted_at: datetime | None
    #: The claimer's display name, or None if they set none or left.
    claimer: str | None
    crew_size: int
    you_are_crew: bool


class CrewMember(BaseModel):
    name: str | None
    you: bool
    hours: float | None


class PhotoView(BaseModel):
    id: uuid.UUID
    phase: str
    point: int | None
    url: str
    created_at: datetime


class ClaimDetail(ClaimSummary):
    started_at: datetime | None
    verified_at: datetime | None
    released_at: datetime | None
    steps_done: list[str]
    notes: str | None
    review_note: str | None
    reviewed_by: str | None
    crew: list[CrewMember]
    photos: list[PhotoView]
    #: True when this caller may review it: submitted, and not on its crew.
    you_may_review: bool


class InviteLink(BaseModel):
    token: str


class JoinClaim(Strict):
    token: Annotated[str, StringConstraints(min_length=16, max_length=128)]


class HoursEntry(Strict):
    hours: Annotated[float, Field(gt=0, le=limits.HOURS_MAX, multiple_of=0.5)]


class Submission(Strict):
    steps_done: list[Step] = Field(default_factory=list, max_length=limits.STEPS_MAX)
    notes: NotesText | None = None


class Review(Strict):
    verdict: Literal["verify", "send_back"]
    note: ReviewNote | None = None


class HoursTotals(BaseModel):
    verified: float
    waiting: float
    claims: int
