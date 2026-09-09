"""The `field_notes` table - dated observations about a place, and the
`note_flags` table that keeps them honest.

See ../../../features/FIELD_NOTES.md for the whole design. The short
version: upstream (ATC's GIS) owns what exists and where; the field owns
what a place is like today; and the two LAYER rather than merge, so nothing
here ever edits an upstream fact. A note is what someone saw, where, and
when they saw it - not a rating, not a thread, not a reply.

A note is visible the moment it lands, which is the opposite default from
`reports` and is argued rather than assumed (FIELD_NOTES.md §5): a note
that waits for review is not fresh, and freshness is the entire feature. A
condition note is low-stakes and self-correcting - the next hiker's note
supersedes it in hours - where a closure is not, which is why closures keep
their queue. Moderation here is flag-and-hide: `hidden_at` set by a
moderator acting on a `NoteFlag`, the row hidden and never deleted, so a
wrong removal is recoverable and a pattern of abuse stays legible.

`observed_at` is not `posted_at`, and the split is the point. Hikers write
at camp or in town days later; a note stamped with its upload time is a lie
the system tells by accident, and it is the exact lie this project cares
most about (value #4's own example is "reported 3 days ago vs. confirmed
today"). Same pair as Report's `timestamp`/`received_at`, renamed to the
design's own words.

`poi_id` follows report.py's precedent exactly: a plain nullable string,
never a ForeignKey, because it is a soft reference into the pipeline's
static POI export - a dataset that lives outside this database entirely.
`lat`/`lon`/`mile` are the fallback anchor, and what re-anchors a note
whose POI id an upstream refresh has orphaned (FIELD_NOTES.md §7).

See app/models/profile.py for the naive-UTC convention every datetime
column here follows.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base
from app.models.report import ReporterType


class Observation(str, enum.Enum):
    """The one-tap tags, all POI types' values in one enum.

    FIELD_NOTES.md scopes them by poi_type - water gets flowing/trickling/
    dry, shelters and campsites fine/problem/trash, resupply open/limited/
    closed, parking open/full/trash, and `not_found` is the dispute value
    every type shares. They live in ONE enum because this backend cannot
    police the pairing: a POI's type is a fact of the published artifact, not
    of any table here, so a per-type check would need data the server does
    not hold. The client's picker only offers the right values; a hand-built
    request that files "dry" on a shelter produces a nonsense note the next
    hiker's note supersedes, which is the same self-correction the whole
    surface leans on.

    `not_found` is deliberately accepted at the wire even though tonight's
    client never sends it: it is FIELD_NOTES.md §4's dispute value, one
    observation among the others rather than a second model, and refusing it
    here would force a schema change the moment the dispute rendering lands.

    `full` IS STILL ACCEPTED AND IS NO LONGER OFFERED ON A SHELTER (#1122).
    The client stopped asking shelters and campsites about capacity - it is
    the number the project already declines to publish - and moved `full` to
    parking, where a hiker can actually see it. Removing it here would be a
    different and worse thing: an old client in the field still sends it, and
    a narrowed request enum is the one enum change scripts/check_openapi_compat.py
    calls a break rather than an addition. Notes already holding it stay
    readable for the same reason.

    NO MIGRATION FOR `trash`. The column is `native_enum=False`, so Postgres
    holds a plain VARCHAR(20) with no CHECK constraint behind it (SQLAlchemy
    creates one only under `create_constraint=True`, which defaults off) -
    there is no database object naming these members, and `alembic check`
    finds no diff. tests/test_migrations.py is what proves that rather than
    this comment.
    """

    # Water
    flowing = "flowing"
    trickling = "trickling"
    dry = "dry"
    # Shelters and campsites
    fine = "fine"
    problem = "problem"
    # Was the shelter/campsite thumbs-down until #1140, and is kept because
    # notes filed under it still say what somebody meant when they tapped it.
    # The word implied structural damage, so a hiker with mice in the food box
    # or a fouled privy had no button - "problem" is the same thumbs-down
    # without the claim. Nothing writes this any more; everything must read it.
    damaged = "damaged"
    # Shelters, campsites and parking - litter somebody left (#1122). Shares
    # its name with the report type it escalates into, because they are the
    # same complaint at two weights.
    trash = "trash"
    # Parking, and shelters before #1122
    full = "full"
    # Resupply, and parking's good end
    open = "open"
    limited = "limited"
    closed = "closed"
    # Any type - the dispute (FIELD_NOTES.md §4)
    not_found = "not_found"


class FieldNote(Base):
    __tablename__ = "field_notes"

    # Client-minted UUID string, the same shape and reason as Report.id: the
    # outbox names the id before the row exists, which is what makes the
    # idempotent retry in routers/field_notes.py possible at all.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    reporter_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

    # Soft reference into the published POI export - see module docstring.
    # Indexed because the card's read and the bake's per-POI roll-up both
    # filter on it.
    poi_id = Column(String, nullable=True, index=True)

    # The fallback anchor. The client fills these from the POI's own
    # coordinates when the note is written from a card, or from the GPS fix
    # when it is not - so an orphaned note is re-anchorable rather than lost.
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    mile = Column(Float, nullable=True)

    # native_enum=False, matching every enum in this schema - see
    # profile.py for why a native enum is the harder one to change later.
    observation = Column(Enum(Observation, native_enum=False, length=20), nullable=True)

    note = Column(Text, nullable=True)

    # When the hiker was there - their claim, bounded at the future end by
    # the schema, unbounded into the past because being off-grid for two
    # weeks is ordinary on a thru-hike.
    observed_at = Column(DateTime, nullable=False, default=utc_now)

    # When it reached this server - always server truth, never the claim.
    posted_at = Column(DateTime, nullable=False, default=utc_now)

    # The only public attribution (FIELD_NOTES.md §6): it informs without
    # identifying. reporter_id above is never serialised to anyone but the
    # author and moderators, and never baked.
    reporter_type = Column(Enum(ReporterType, native_enum=False, length=20), nullable=False)

    # Flag-and-hide (FIELD_NOTES.md §5). Set means hidden from every public
    # read and from the bake; the row is kept, never deleted, so a wrong
    # removal is recoverable. Indexed because every public read filters on
    # IS NULL.
    hidden_at = Column(DateTime, nullable=True, index=True)
    hidden_by = Column(String, ForeignKey("profiles.id"), nullable=True)

    # The photo DATA_NUDGES.md's opted-in mode promises (#879), and the three
    # columns that make publishing it immediately defensible.
    #
    # **Publish-now, screened on device** - the maintainer's 2026-08-21
    # decision. A note is public the moment it lands and its photo goes with
    # it, because a photo that arrives days after the note it illustrates is
    # not evidence of what the note says. There is deliberately NO cooling-off
    # window here, unlike a community share: the note is the unit, and a
    # picture appearing two hours after the sentence it belongs to would be a
    # card that changes its story while a hiker reads it.
    #
    # `photo_uploaded_at` is null until the bytes land - the same two-phase
    # flush every photo in this app uses, because the row and the bytes are
    # two requests and the second one is the one with no signal.
    photo_uploaded_at = Column(DateTime, nullable=True)

    # What the phone's own check found (lib/photoScreen.ts), or null for
    # "nothing found OR could not look" - one value on purpose, because the
    # queued note must not distinguish them. It never decides anything: #837's
    # posture is flag, never block.
    photo_flagged = Column(String, nullable=True)

    # The one human glance a nudity flag waits on, mirroring PoiPhoto's
    # `reviewed_at` in name and meaning rather than inventing a second
    # vocabulary. `poi_photos.py`'s `_held()` is the rule this copies: only
    # the nudity case is held, a face flag sorts the queue and publishes.
    photo_reviewed_at = Column(DateTime, nullable=True)
    photo_reviewed_by = Column(String, ForeignKey("profiles.id"), nullable=True)


def note_photo_held(note: "FieldNote") -> bool:
    """Whether this note's photo is waiting on a person before anyone sees it.

    The narrow hold the decided posture allows, reaching only what the phone
    itself flagged as nudity. A face flag is not held: it orders the queue.
    Spelled as a function rather than a column so the rule lives in one place
    - `poi_photos.py` learned that the hard way with its three-valued-logic
    complement.
    """
    return note.photo_flagged == "nudity" and note.photo_reviewed_at is None


class NoteFlag(Base):
    """One reader saying a note needs a moderator's eyes.

    Flagging is the whole moderation entry point for notes - moderators see
    only what is flagged (FIELD_NOTES.md §5), so this table is the queue's
    source rather than an audit sidecar. A flag never hides anything by
    itself; a person does.
    """

    __tablename__ = "note_flags"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    note_id = Column(String, ForeignKey("field_notes.id"), nullable=False, index=True)
    flagged_by = Column(String, ForeignKey("profiles.id"), nullable=False)

    # Free text, capped at the wire (schemas/common.NoteText). Optional: "this
    # is wrong" with no essay is a complete flag.
    reason = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
