"""Request and response models for `/clubs/{slug}/inventory`.

First written for #1984 — A club's enrolment, settings and waiver have
endpoints, and an enrolled volunteer is a person `org_access` did not know
about.

features/STRUCTURE_INVENTORY.md is the design. Enrolment and the club's
settings (#1984), an observation's upload (#1985) and its photos (#1986);
areas, claims, passes, the review queue and the exports arrive with their
own issues.

**What the wire refuses to carry is part of the design.** `EnrollmentCreate`
has no time field: the server stamps the signature, so a phone's clock can
never backdate one. `EnrollmentPatch` can only say the field guide is
finished, never that it is not. `InventorySettingsIn` has no
`publish_locations`: whether a club can publish structure locations at all
in v1 is the design doc's open question 5, and a switch that publishes
nothing yet would be a switch that lies.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.core.time import UtcDatetime
from app.models.inventory import (
    Condition,
    Connection,
    FixSource,
    Repair,
    RepairTiming,
    ReviewState,
    SizeMethod,
    StructureKind,
)
from app.schemas.common import FiniteFloat, NoteText

# A name as typed under the club's waiver. Long enough for anybody's full
# name, short enough that the field cannot be used to store something else.
# A bound on input, not a finding about names.
TYPED_NAME_MAX_CHARS = 200
TypedName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TYPED_NAME_MAX_CHARS)]

# A club's own label for a waiver text, like "2026-1". Bounded for the same
# reason as the name.
WaiverVersion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]

# The waiver itself. A real club waiver runs to a page or two; 20,000
# characters is several times that and still a bound. Not measured.
WAIVER_MAX_CHARS = 20_000
WaiverText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=WAIVER_MAX_CHARS)]


class EnrollmentCreate(BaseModel):
    """Signing the club's waiver, which is what enrolling is.

    `waiver_version` is the version the volunteer was shown. It must match
    the club's current version, so a signature always names the text it was
    given against.
    """

    typed_name: TypedName
    waiver_version: WaiverVersion


class EnrollmentPatch(BaseModel):
    """The field guide is finished. There is no way to say it is not."""

    training_completed: Literal[True]


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    waiver_version: str
    waiver_signed_at: UtcDatetime
    typed_name: str
    training_completed_at: UtcDatetime | None
    field_day_at: UtcDatetime | None
    #: Waiver signed and field guide finished: what the survey's own
    #: endpoints require. Derived, so it cannot disagree with the columns.
    can_survey: bool


class InventorySettingsOut(BaseModel):
    """A club's survey settings, readable by anybody signed in.

    The waiver has to be readable before somebody signs it, and the
    thresholds are the rule the Coverage screen states in words - neither is
    a secret. `enrolment_open` is false until the club has written a waiver
    and a version.
    """

    waiver_text: str | None
    waiver_version: str | None
    claim_days_ahead: int
    coverage_window_days: int
    coverage_min_records: int
    stale_days: int
    publish_locations: bool
    enrolment_open: bool


class InventorySettingsIn(BaseModel):
    """What a club admin sets.

    The bounds keep a typo from becoming a rule - a claim window of 0, a
    coverage window of 9,000 days. They are bounds on input, not findings;
    the defaults the columns start from are the `@unvalidated` thresholds in
    app/models/inventory.py.
    """

    waiver_text: WaiverText | None = None
    waiver_version: WaiverVersion | None = None
    claim_days_ahead: int = Field(ge=1, le=60)
    coverage_window_days: int = Field(ge=7, le=730)
    coverage_min_records: int = Field(ge=1, le=50)
    stale_days: int = Field(ge=30, le=3650)


# --- An observation's upload (#1985) ---------------------------------------

# Bounds on input, not findings. The phone samples for up to 40 seconds
# (the design doc's numbers table, @unvalidated); 600 readings is ten a
# second for a minute, far past anything that sampling produces, and still a
# ceiling on a JSON column a phone fills.
MAX_READINGS = 600
MAX_READINGS_SECONDS = 3600
MAX_PROBLEMS = 20

# A tag key from a type's field card, or a count's name: `abutment_eroded`,
# `sleeps`. Lowercase words, so a key can never carry a sentence.
TagKey = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")]
ShortLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Latitude = Annotated[FiniteFloat, Field(ge=-90, le=90)]
Longitude = Annotated[FiniteFloat, Field(ge=-180, le=180)]


class Reading(BaseModel):
    """One GPS sample, as the phone took it. Every one is kept (rule 2)."""

    lat: Latitude
    lon: Longitude
    acc: Annotated[FiniteFloat, Field(ge=0)]
    t: FiniteFloat


class ObservationCreate(BaseModel):
    """One visit to one structure, as the outbox sends it.

    **`id` is the client's**, so a retry is the same row: the outbox names
    the record before the server has seen it. `structure_id` is the client's
    too when the structure is new, and then `kind` says what it is.

    **There is no `readings_count`.** The server counts `readings`, so the
    count and the readings kept beside it cannot disagree. There is no
    `mile` and no distance to the line either: those are the server's,
    computed from the club's own section line (the design doc's conflict 1).

    **A size is a bucket or a measurement, never both** (rule 3). A bucket
    carries no number, so nothing a volunteer estimated can come back out of
    the database in the voice of a tape measure.
    """

    id: uuid.UUID
    structure_id: uuid.UUID
    kind: StructureKind | None = None
    subkind: ShortLabel | None = None
    pass_id: uuid.UUID | None = None

    captured_at: datetime
    offline: bool = False

    lat: Latitude
    lon: Longitude
    accuracy_m: Annotated[FiniteFloat, Field(ge=0)]
    readings: Annotated[list[Reading], Field(min_length=1, max_length=MAX_READINGS)]
    readings_seconds: Annotated[int, Field(ge=0, le=MAX_READINGS_SECONDS)]
    fix_source: FixSource = FixSource.sampled
    gps_lock: bool | None = None
    satellites: Annotated[int, Field(ge=0, le=200)] | None = None
    connection: Connection = Connection.unknown

    same_as_structure_id: uuid.UUID | None = None

    condition: Condition
    problems: Annotated[list[TagKey], Field(max_length=MAX_PROBLEMS)] = []
    repair: Repair
    timing: RepairTiming | None = None

    size_method: SizeMethod | None = None
    size_bucket: ShortLabel | None = None
    size_measured: Annotated[FiniteFloat, Field(gt=0)] | None = None
    size_unit: Literal["ft", "m"] | None = None
    counts: dict[TagKey, Annotated[int, Field(ge=0, le=10_000)]] | None = None
    railings: bool | None = None

    notes: NoteText | None = None

    @field_validator("captured_at")
    @classmethod
    def _reject_a_future_capture(cls, value: datetime) -> datetime:
        """Phone clocks drift, so a small lead is skew; `ReportCreate`'s rule."""
        compared = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if compared > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("captured_at cannot be in the future")
        return value

    @model_validator(mode="after")
    def _a_size_says_how_it_was_arrived_at(self) -> "ObservationCreate":
        if self.size_method is None:
            if self.size_bucket is not None or self.size_measured is not None or self.size_unit is not None:
                raise ValueError("a size needs its size_method: bucket or tape")
        elif self.size_method is SizeMethod.bucket:
            if self.size_bucket is None:
                raise ValueError("a bucket size needs its size_bucket")
            if self.size_measured is not None or self.size_unit is not None:
                raise ValueError("a bucket is an estimate and carries no number")
        elif self.size_measured is None or self.size_unit is None:
            raise ValueError("a measured size needs its number and its unit")
        return self

    @model_validator(mode="after")
    def _leaving_it_has_no_how_soon(self) -> "ObservationCreate":
        if self.repair is Repair.leave and self.timing is not None:
            raise ValueError("timing says how soon a repair is needed, and 'leave' asks for none")
        return self


class ObservationReceipt(BaseModel):
    """What the outbox needs back: which rows hold the record, and its state.

    `mile` and `off_line_ft` are null until the server has computed them on
    accept (#1987); the phone never sends them.
    """

    observation_id: str
    structure_id: str
    review_state: ReviewState
    mile: float | None
    off_line_ft: float | None


class InventoryPhotoReceipt(BaseModel):
    """What a photo upload tells the outbox: how far the record's set now runs."""

    observation_id: str
    photo_count: int


class InventoryPhotoLink(BaseModel):
    """A short-lived URL for one of a record's photos, `ReportPhotoLink`'s shape.

    A bearer capability for the object, which is why it is asked for with a
    token and answered with a URL that expires.
    """

    url: str
    expires_in: int
