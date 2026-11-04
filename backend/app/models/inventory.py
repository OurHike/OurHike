"""The structure inventory: a club's built things, and every visit to them.

See ../../../features/STRUCTURE_INVENTORY.md for the whole design. The rule
these tables exist to keep is the first of its six: **nothing is
overwritten.** A structure is one row; every visit to it is a new
`InventoryObservation`, append-only, with the volunteer, the time and the
review state. "Current condition" is the latest accepted observation - a
query, not a column - so two volunteers logging the same bridge on the same
day is two rows and free data, never a conflict somebody has to adjudicate.
`features/FIELD_NOTES.md`'s layering rule, applied to a club's own
structures.

Six tables, all locked by row-level security in the revision that creates
them (`f2b9d4c7e1a3`), because a table PostgREST can see is a table the
anon key can read until RLS says otherwise:

    inventory_enrollments    a volunteer's standing in one club's programme
    inventory_structures     one physical thing on the trail
    inventory_observations   one visit to one structure
    inventory_passes         one walk of one stretch by one volunteer
    inventory_claims         a heads-up that somebody means to walk a section
    inventory_club_settings  one row per club: the waiver and the thresholds

**Enums are `native_enum=False` with a length, and there is no CHECK
constraint behind them.** That is this schema's convention as Postgres
actually holds it: migrated to head `e4b8d2a7c391` on 2026-11-04, the
public schema had no CHECK constraints at all, and `field_notes.observation`
is a plain VARCHAR(20), as `field_note.py` says. Values are validated by
Pydantic at the edge and by the Enum in the session.
`tests/test_column_conventions.py`'s header says "VARCHAR WITH A CHECK", and
so did the issue title this module was written for (#1983); both describe
a constraint nobody creates.

**Photos have no table.** The R2 object is derived and disposable, and the
observation row is authoritative - `photo_count` is all the row learns,
`app/core/photos.py`'s own sentence for reports.

Timestamps are naive UTC from `utc_now()`, as everywhere else here
(`app/models/profile.py`).
"""

import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.core.time import utc_now
from app.db.base import Base

# --- The thresholds a club starts with ------------------------------------
#
# Each is the default for its column on `inventory_club_settings`, so a club
# can change it without a release. None of them was measured.

# How far ahead a volunteer may claim a day on a section, counted in days
# from today. @unvalidated: the maintainer's own figure from design review
# (SPEC.md's data model). What would settle it: whether claims made more
# than a week ahead are walked on the day claimed.
MAX_CLAIM_DAYS_AHEAD = 14

# A section needs a walk when it has fewer than COVERAGE_MIN_RECORDS records
# in the last COVERAGE_WINDOW_DAYS days. @unvalidated: the design's pick
# (SPEC.md, decision "Where to walk"). What would settle it: a pilot season,
# and whether the sections it marks are the ones the Local Chair would have
# named as thin.
COVERAGE_WINDOW_DAYS = 90
COVERAGE_MIN_RECORDS = 3

# A section with no record in this many days is highlighted on the coverage
# map. @unvalidated, the same pick and the same pilot season settles it.
STALE_DAYS = 365


class StructureKind(str, enum.Enum):
    """The twelve tiles on the "What is it?" screen (2b).

    `other` carries the small drainage works - water bars, check dams,
    drainage dips, cairns - and anything else a crew built. The trail itself
    going wrong is a Report a Problem, not a structure.
    """

    bridge = "bridge"
    puncheon = "puncheon"
    shelter = "shelter"
    privy = "privy"
    campsite = "campsite"
    water = "water"
    blaze = "blaze"
    sign = "sign"
    kiosk = "kiosk"
    parking = "parking"
    steps = "steps"
    other = "other"


class StructureStatus(str, enum.Enum):
    active = "active"
    # Gone from the ground. The row stays, with every visit that saw it.
    removed = "removed"
    # Turned out to be another structure; `merged_into_id` says which. A
    # merge joins two structures and never edits an observation.
    merged = "merged"


class FixSource(str, enum.Enum):
    # Sampled standing at the structure: the Location screen's default.
    sampled = "sampled"
    # "Can't stand at it? Mark it from here": the readings are where the
    # volunteer stood, not where the structure is, and the record says so.
    marked_from_here = "marked_from_here"


class Connection(str, enum.Enum):
    """What `navigator.connection` said, where it exists.

    It does on Android Chrome and does not on iOS, so `unknown` is an
    ordinary value here and not a failure (the design doc's conflict 4).
    """

    cellular = "cellular"
    wifi = "wifi"
    none = "none"
    unknown = "unknown"


class Condition(str, enum.Enum):
    """Good, Fair, Poor, Unsafe - with their definitions on screen (2f)."""

    good = "good"
    fair = "fair"
    poor = "poor"
    unsafe = "unsafe"


class Repair(str, enum.Enum):
    """The volunteer's suggestion. The Local Chair decides what happens."""

    leave = "leave"
    minor = "minor"
    major = "major"
    replace = "replace"
    remove = "remove"


class RepairTiming(str, enum.Enum):
    now = "now"
    this_season = "this_season"
    next_year = "next_year"
    five_years = "five_years"


class SizeMethod(str, enum.Enum):
    """How a size was arrived at, which travels with it to the CSV (rule 3).

    Length 6, not the 5 SPEC.md's data model gives it: `bucket` is six
    characters, and `tests/test_column_conventions.py` would refuse 5.
    """

    bucket = "bucket"
    tape = "tape"


class ReviewState(str, enum.Enum):
    """The report pattern's states, renamed for a club reviewing its own."""

    submitted = "submitted"
    accepted = "accepted"
    # "Send back": the record goes back to its volunteer with the note.
    returned = "returned"
    merged = "merged"
    not_ours = "not_ours"


class PassState(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class InventoryEnrollment(Base):
    """A volunteer's standing in one club's survey programme.

    **The row is the signature.** It is written when the volunteer signs the
    club's waiver by typed name (screen 1b), so the waiver columns are never
    empty: there is no "joined but not signed" state worth keeping. What the
    row records is which version of the club's text was signed, when, and
    the name as typed. Whether that is the club's legal record is counsel's
    question, not this table's (the design doc's open question 3).

    The survey's volunteer need not hold a maintainer assignment, which is
    why `app/core/org_access.py` does not know them and this table does.
    """

    __tablename__ = "inventory_enrollments"
    __table_args__ = (UniqueConstraint("club_id", "person_id", name="uq_inventory_enrollments_club_person"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)
    person_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

    waiver_version = Column(String, nullable=False)
    waiver_signed_at = Column(DateTime, nullable=False, default=utc_now)
    typed_name = Column(Text, nullable=False)

    # Set when the field guide is finished. Until then the volunteer can read
    # the cards and cannot submit.
    training_completed_at = Column(DateTime, nullable=True)
    # A club's in-person field day, when it runs one. Optional, never required.
    field_day_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)


class InventoryStructure(Base):
    """One physical thing on the trail.

    `lat`/`lon` come from the observation that created the row and move to
    the latest accepted observation's on each accept, so a new structure is
    placeable in the review queue before anybody has accepted it.

    `mile` and `off_line_ft` are the server's, computed from the club's own
    section line (the design doc's conflict 1). The phone never sends them.
    """

    __tablename__ = "inventory_structures"
    __table_args__ = (UniqueConstraint("club_id", "code", name="uq_inventory_structures_club_code"),)

    # The client's id when a volunteer logs a structure nobody has seen: the
    # outbox names it before the row exists, as `Report.id` does.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)
    trail_id = Column(String, ForeignKey("org_trails.id"), nullable=True, index=True)
    section_id = Column(String, ForeignKey("org_sections.id"), nullable=True, index=True)

    kind = Column(Enum(StructureKind, native_enum=False, length=10), nullable=False)
    subkind = Column(String, nullable=True)

    # Readable and unique per club, `<trail>-<state>-<kind>-<n>` like
    # `AT-NY-BR-014`, assigned on the structure's first accepted
    # observation. Null until then; Postgres's unique constraint lets any
    # number of rows share a null.
    code = Column(String, nullable=True)
    # Ids the same thing already has elsewhere: {"atc": ..., "nps": ...,
    # "guidebook": ...}. Each body numbers structures its own way.
    external_ids = Column(JSON, nullable=True)

    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    mile = Column(Float, nullable=True)
    off_line_ft = Column(Float, nullable=True)

    # A published POI id when one matches. A soft reference into the
    # pipeline's export, never a foreign key - report.py's precedent.
    poi_id = Column(String, nullable=True)

    status = Column(Enum(StructureStatus, native_enum=False, length=8), nullable=False, default=StructureStatus.active)
    merged_into_id = Column(String, ForeignKey("inventory_structures.id"), nullable=True)

    # Club-private unless the club switches publication on, and then only
    # kind, position and code - never condition, notes or photos.
    published = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    created_by = Column(String, ForeignKey("profiles.id"), nullable=False)


class InventoryPass(Base):
    """One walk of one stretch by one volunteer.

    The `SurveyPass` features/INVASIVE_SPECIES.md sketched, built here first.
    `to_lat`/`to_lon` are where the walk really ended, which the Finish
    screen lets the volunteer place when they stopped early - so the pass
    says what was walked, not what was meant to be.
    """

    __tablename__ = "inventory_passes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)
    volunteer_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
    trail_id = Column(String, ForeignKey("org_trails.id"), nullable=False)

    started_at = Column(DateTime, nullable=False, default=utc_now)
    finished_at = Column(DateTime, nullable=True)

    # Null when the phone had no fix at that moment. Absent means unknown.
    from_lat = Column(Float, nullable=True)
    from_lon = Column(Float, nullable=True)
    to_lat = Column(Float, nullable=True)
    to_lon = Column(Float, nullable=True)

    ended_early = Column(Boolean, nullable=False, default=False)
    state = Column(Enum(PassState, native_enum=False, length=11), nullable=False, default=PassState.in_progress)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)


class InventoryObservation(Base):
    """One visit to one structure. Append-only.

    **Every GPS reading the phone took is kept** (`readings`, as
    `[{lat, lon, acc, t}]`), because the phone records what it knows and
    nothing it assumes (rule 2). `lat`/`lon` are their median, with
    `accuracy_m`, `readings_count` and `readings_seconds` beside it.

    **A size is saved with how it was arrived at** (rule 3): a bucket is a
    guess and says so in `size_method`, all the way to the export.

    **Unsafe sets nothing special on the row.** The queue orders by it, the
    Report a Problem it files is linked by `report_id`, and the email to the
    club's admins is sent on upload. A flag column would be a second source
    for a fact `condition` already holds.

    `mile` and `off_line_ft` are the server's, filled on accept.
    """

    __tablename__ = "inventory_observations"
    __table_args__ = (
        # The review queue reads a club's observations by state; cheap while
        # the table is small, which is when adding it is a line rather than
        # an incident (c3a8f1d6e2b7's reasoning).
        Index("ix_inventory_observations_club_review_state", "club_id", "review_state"),
    )

    # The client's id. Upload is idempotent on it: a second POST with the
    # same id answers the same row and changes nothing (the outbox's rule).
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    structure_id = Column(String, ForeignKey("inventory_structures.id"), nullable=False, index=True)
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)
    pass_id = Column(String, ForeignKey("inventory_passes.id"), nullable=True, index=True)
    volunteer_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

    # The phone's clock when the volunteer saved it, which may be days
    # before the upload. `created_at` is when it reached the server.
    captured_at = Column(DateTime, nullable=False)
    offline = Column(Boolean, nullable=False, default=False)

    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    accuracy_m = Column(Float, nullable=False)
    readings_count = Column(Integer, nullable=False)
    readings_seconds = Column(Integer, nullable=False)
    readings = Column(JSON, nullable=False)
    fix_source = Column(Enum(FixSource, native_enum=False, length=16), nullable=False, default=FixSource.sampled)

    # What the platform could tell. Null is "the platform did not say" and
    # never false or zero: no platform this build reaches reports a
    # satellite count (the design doc's conflict 4).
    gps_lock = Column(Boolean, nullable=True)
    satellites = Column(Integer, nullable=True)
    connection = Column(Enum(Connection, native_enum=False, length=8), nullable=False, default=Connection.unknown)

    # The volunteer's answer on "Is this the same one?" (2i). Nothing is
    # merged on the phone; a reviewer decides.
    same_as_structure_id = Column(String, ForeignKey("inventory_structures.id"), nullable=True)

    condition = Column(Enum(Condition, native_enum=False, length=6), nullable=False)
    # Tag keys from the type's field card, in the card's order.
    problems = Column(JSON, nullable=False, default=list)
    repair = Column(Enum(Repair, native_enum=False, length=7), nullable=False)
    # Null when the suggestion is to leave it: there is no "how soon" for
    # nothing.
    timing = Column(Enum(RepairTiming, native_enum=False, length=11), nullable=True)

    # Size is optional ("Skip this"), so every size column is nullable, and
    # null means nobody said - never zero.
    size_bucket = Column(String, nullable=True)
    size_measured = Column(Float, nullable=True)
    size_unit = Column(String, nullable=True)
    size_method = Column(Enum(SizeMethod, native_enum=False, length=6), nullable=True)
    # Per type: sleeps, sites, cars, risers, rings.
    counts = Column(JSON, nullable=True)
    railings = Column(Boolean, nullable=True)

    notes = Column(Text, nullable=True)
    photo_count = Column(Integer, nullable=False, default=0)

    review_state = Column(Enum(ReviewState, native_enum=False, length=9), nullable=False, default=ReviewState.submitted)
    reviewed_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)

    # The Report a Problem an Unsafe observation filed, when it filed one.
    report_id = Column(String, ForeignKey("reports.id"), nullable=True)

    mile = Column(Float, nullable=True)
    off_line_ft = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)


class InventoryClaim(Base):
    """A heads-up that a volunteer means to walk a section on a day.

    Modelled on `ridge_runner_commitments`: a window, a cap, and **no column
    for what was expected.** A claim is current while `walk_on` is today or
    later and it has not been released; nothing expires a row, the query
    does. Nobody is told a claim lapsed, because a claim is not a promise.
    """

    __tablename__ = "inventory_claims"
    __table_args__ = (
        # The areas query reads a section's claims from today forward.
        Index("ix_inventory_claims_section_walk_on", "section_id", "walk_on"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)
    volunteer_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
    section_id = Column(String, ForeignKey("org_sections.id"), nullable=False)

    claimed_at = Column(DateTime, nullable=False, default=utc_now)
    walk_on = Column(Date, nullable=False)
    released_at = Column(DateTime, nullable=True)


class InventoryClubSettings(Base):
    """One row per club: its waiver, and the thresholds it can change.

    The waiver columns are nullable because an admin can save thresholds
    before the club's text is ready; enrolment stays closed while either is
    empty. Mark, accent colour and units are not here: they wait for the
    general branding block, which the volunteers console wants too.
    """

    __tablename__ = "inventory_club_settings"

    club_id = Column(String, ForeignKey("clubs.id"), primary_key=True)

    waiver_text = Column(Text, nullable=True)
    waiver_version = Column(String, nullable=True)

    claim_days_ahead = Column(Integer, nullable=False, default=MAX_CLAIM_DAYS_AHEAD)
    coverage_window_days = Column(Integer, nullable=False, default=COVERAGE_WINDOW_DAYS)
    coverage_min_records = Column(Integer, nullable=False, default=COVERAGE_MIN_RECORDS)
    stale_days = Column(Integer, nullable=False, default=STALE_DAYS)

    publish_locations = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
