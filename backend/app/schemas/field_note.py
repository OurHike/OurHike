"""Pydantic request/response models for the `/field-notes` router."""

import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.time import UtcDatetime
from app.models.field_note import FieldNote, Observation
from app.models.profile import MODERATOR_ROLES, Profile
from app.models.report import ReporterType
from app.schemas.common import FiniteFloat, NoteText


class FieldNoteCreate(BaseModel):
    """The client-submitted shape of a new field note.

    The same three sanctioned client claims `ReportCreate` documents, for
    the same offline-first reasons: `id` is an idempotency key (the outbox
    mints one per item, so a resend is recognisably the same note),
    `observed_at` is the moment of writing rather than of sending (bounded
    at the future end, deliberately unbounded into the past), and `mile` is
    knowable on the phone and nowhere else. `posted_at`, `reporter_id` and
    the hidden pair are all server-assigned and have no fields here.

    A note with only a tag is fine, and a note with only text is fine
    (FIELD_NOTES.md §1) - but a note with neither says nothing to the next
    hiker and is refused as the empty submission it is.
    """

    id: uuid.UUID | None = None

    poi_id: str | None = None
    lat: FiniteFloat | None = None
    lon: FiniteFloat | None = None
    mile: FiniteFloat | None = None

    observation: Observation | None = None
    note: NoteText | None = None

    observed_at: datetime | None = None
    reporter_type: ReporterType

    @model_validator(mode="after")
    def _require_something_observed(self) -> "FieldNoteCreate":
        # Whitespace-only text is the same empty note wearing a spacebar.
        if self.observation is None and (self.note is None or self.note.strip() == ""):
            raise ValueError("a note needs an observation tag or some text")
        return self

    @field_validator("observed_at")
    @classmethod
    def _reject_future_observation(cls, value: datetime | None) -> datetime | None:
        # Same rule and same skew allowance as ReportCreate.authored_at:
        # phone clocks drift, so a small lead is skew rather than tampering.
        if value is None:
            return None
        skew = timedelta(minutes=5)
        now = datetime.now(timezone.utc)
        compared = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if compared > now + skew:
            raise ValueError("observed_at cannot be in the future")
        return value

    @field_validator("mile")
    @classmethod
    def _reject_an_impossible_mile(cls, value: float | None) -> float | None:
        # ReportCreate's rule, verbatim: bounded at the one end this server
        # can bound, with no upper bound because the trail's length is the
        # published centerline's property, not this backend's.
        if value is None:
            return None
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("mile must be a real number")
        if value < 0:
            raise ValueError("mile cannot be negative")
        return value


class FieldNoteOut(BaseModel):
    """One note, as much of it as the caller is entitled to.

    Built with `for_viewer`, never by returning the ORM row - ReportOut's
    posture, kept for the same reason. Two fields are withheld from anyone
    who is neither the author nor a moderator, and the second matters more
    here than on reports: many dated notes along a corridor from one
    identifier reconstruct a hike (FIELD_NOTES.md §6, and #252 for what
    removing that pair from reports cost). `reporter_type` is the public
    attribution by design - it informs without identifying.

    `hidden_at` is deliberately absent even for moderators: the moderation
    surface has its own shape below, and the public one must not grow a
    field whose null means "not for you" on one row and "not hidden" on
    another.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    poi_id: str | None
    lat: float | None
    lon: float | None
    mile: float | None
    observation: Observation | None
    note: str | None
    observed_at: UtcDatetime
    reporter_type: ReporterType

    # ---- Withheld from the public. Null is "not for you", not "unset". ----

    reporter_id: str | None = None
    # The second clock. `observed_at` is public and exact; the pair narrows
    # "when did this person have signal" - ReportOut withholds received_at
    # on the same grounds.
    posted_at: UtcDatetime | None = None

    @classmethod
    def for_viewer(cls, note: "FieldNote", viewer: "Profile | None") -> "FieldNoteOut":
        privileged = viewer is not None and (note.reporter_id == viewer.id or viewer.role in MODERATOR_ROLES)
        return cls(
            id=note.id,
            poi_id=note.poi_id,
            lat=note.lat,
            lon=note.lon,
            mile=note.mile,
            observation=note.observation,
            note=note.note,
            observed_at=note.observed_at,
            reporter_type=note.reporter_type,
            reporter_id=note.reporter_id if privileged else None,
            posted_at=note.posted_at if privileged else None,
        )


class NoteFlagCreate(BaseModel):
    """A reader asking for a moderator's eyes. The reason is optional -
    "this is wrong" with no essay is a complete flag."""

    reason: NoteText | None = None


class FlaggedNoteOut(BaseModel):
    """One queue entry for the moderation surface: the note, how many people
    flagged it, what they said, and whether it is currently hidden.

    Moderator-only by construction (the router gates the endpoint), so the
    note rides along whole - including `reporter_id`, which the queue needs
    for exactly the reason reports' queue gets it: a pattern of abuse is a
    pattern across one account's notes.
    """

    note: FieldNoteOut
    flag_count: int
    # Every distinct reason given, oldest first, empty strings dropped.
    reasons: list[str]
    hidden: bool
