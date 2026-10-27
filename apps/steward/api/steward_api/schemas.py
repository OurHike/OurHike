"""Request and response bodies. Every string a person types is bounded and
stripped of control characters here, so nothing downstream has to remember to."""

from __future__ import annotations

import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from steward_api import limits

_HIDDEN = ("Cc", "Cf", "Co", "Cs", "Cn")


def _no_control_characters(value: str) -> str:
    """Refuses control characters, and the invisible format characters a name
    can use to pass for another: bidi overrides, zero-width joiners and the
    like (Unicode categories Cc, Cf, Co, Cs and Cn; the review's finding 10)."""
    if any(unicodedata.category(ch) in _HIDDEN for ch in value):
        raise ValueError("must not contain control or invisible formatting characters")
    return value


def _no_control_characters_but_line_breaks(value: str) -> str:
    """The same, for notes, which may run over several lines."""
    return _no_control_characters(value.replace("\r\n", "\n").replace("\n", " ")) and value


def _text(max_length: int, *, multiline: bool = False) -> type[str]:
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
        AfterValidator(_no_control_characters_but_line_breaks if multiline else _no_control_characters),
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
NotesText = _text(limits.NOTES_MAX, multiline=True)
ReviewNote = _text(limits.REVIEW_NOTE_MAX, multiline=True)


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
    #: After photos older than this do not count toward the next submission.
    sent_back_at: datetime | None
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
    #: verify: the work is done. send_back: nearly, and here is what is missing.
    #: reject: it was not done, and the site goes back to Open for someone else.
    verdict: Literal["verify", "send_back", "reject"]
    note: ReviewNote | None = None


class HoursTotals(BaseModel):
    verified: float
    waiting: float
    claims: int
