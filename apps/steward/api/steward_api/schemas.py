"""Request and response bodies. Every string a person types is bounded and
stripped of control characters here, so nothing downstream has to remember to."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

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
