"""Pydantic request/response models for the `/field-notes` router."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.photos import note_photo_key, photo_storage_configured, presigned_object_url
from app.core.time import UtcDatetime
from app.models.field_note import FieldNote, Observation, note_photo_held
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

    # What the phone's own check found before the photo left it (#879/#837),
    # or absent for "nothing found OR could not look" - one value on purpose,
    # because a note whose screen failed must be indistinguishable from one
    # whose screen was clean. It never blocks anything: only `nudity` holds
    # the photo, and only until one person looks.
    #
    # Accepted on the note rather than on the upload because the note is what
    # the outbox flushes first, and a verdict that arrived after the bytes
    # would be a hold applied to a photo already public.
    photo_flagged: Literal["nudity", "faces"] | None = None

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

    # The photo (#879), presigned and short-lived, or null. Null covers four
    # different things on purpose - no photo was attached, the bytes never
    # landed, the photo is held on a nudity flag, or this server has no photo
    # storage configured - because none of them is a fact a reader of a card
    # can act on differently, and spelling them apart would tell a stranger
    # that a held photo exists.
    photo_url: str | None = None

    # ---- Withheld from the public. Null is "not for you", not "unset". ----

    reporter_id: str | None = None
    # The second clock. `observed_at` is public and exact; the pair narrows
    # "when did this person have signal" - ReportOut withholds received_at
    # on the same grounds.
    posted_at: UtcDatetime | None = None

    # Whether a photo is on this note but waiting on a person. Privileged
    # only, and it is what lets the moderation queue offer the glance the
    # hold is waiting for. A public reader gets `photo_url: null` and no
    # hint that anything is behind it - "there is a held photo here" is a
    # sentence only the author and a moderator have any use for.
    photo_held: bool = False

    @classmethod
    def for_viewer(cls, note: "FieldNote", viewer: "Profile | None") -> "FieldNoteOut":
        privileged = viewer is not None and (note.reporter_id == viewer.id or viewer.role in MODERATOR_ROLES)
        held = note_photo_held(note)
        # A held photo is served to the author and to moderators and to
        # nobody else: the author because it is theirs and they should see
        # what is waiting, a moderator because looking IS the review the hold
        # exists for. Everyone else reads the note without it, which is the
        # state every note was in before this shipped.
        shows_photo = note.photo_uploaded_at is not None and (not held or privileged)
        return cls(
            id=note.id,
            photo_url=note_photo_url(note) if shows_photo else None,
            photo_held=held if privileged else False,
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


def note_photo_url(note: "FieldNote") -> str | None:
    """A short-lived link to this note's photo, or null.

    Null rather than a raised error when storage is not configured: a
    deployment without a photo bucket still serves notes, and a card that
    500s because a picture is missing would cost a hiker the sentence about
    the spring to protect a photo of it.
    """
    if not photo_storage_configured():
        return None
    try:
        return presigned_object_url(note_photo_key(note.id))
    except Exception:  # noqa: BLE001 - see the docstring: never fatal.
        return None


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
