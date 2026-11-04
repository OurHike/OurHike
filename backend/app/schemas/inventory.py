"""Request and response models for `/clubs/{slug}/inventory` (#1984).

features/STRUCTURE_INVENTORY.md is the design. Only enrolment and the club's
settings live here so far; observations, photos, areas, claims, passes, the
review queue and the exports arrive with their own issues.

**What the wire refuses to carry is part of the design.** `EnrollmentCreate`
has no time field: the server stamps the signature, so a phone's clock can
never backdate one. `EnrollmentPatch` can only say the field guide is
finished, never that it is not. `InventorySettingsIn` has no
`publish_locations`: whether a club can publish structure locations at all
in v1 is the design doc's open question 5, and a switch that publishes
nothing yet would be a switch that lies.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.time import UtcDatetime

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
