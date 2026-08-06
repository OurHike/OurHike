"""The `report` table - community-submitted trail condition reports.

See ../../../features/REPORT_A_PROBLEM.md for the full feature this
mirrors: six report types covering trail/infrastructure conditions, one
location mechanism (an existing map POI id, or a dropped/GPS pin), and a
status/visibility pair that feeds the moderation queue MAP_OPTIONS.md's
closures and HIKER_SAFETY.md's warning escalation both reuse rather than
building a second review workflow (see that doc's "Architecture fit"
section).

`poi_id` is deliberately a plain nullable string, not a SQLAlchemy
`ForeignKey` - it's a soft reference into the pipeline's static POI export
(e.g. "atc_shelters:12345"), a dataset that lives outside this database
entirely (see ../../../TECHNICAL_ARCHITECTURE.md), so there's no local
table for a real FK to point at.

`visibility` is set server-side from `type` alone, never accepted from the
client: `bad_hikers` reports on *people*, not trail conditions - a
meaningfully different risk profile (REPORT_A_PROBLEM.md's "Bad hikers
needs different handling" section) - so it defaults to `internal_only`
while the other five types default to `public`. `severity` likewise has no
client-facing input in v1; it stays `normal` until a later verify action
(HIKER_SAFETY.md's moderator-escalated severity tier, built elsewhere) can
raise it - there's no field for it on the create schema at all.

See app/models/profile.py for the naive-UTC convention every datetime
column here follows, and the open question about it.
"""

import enum
import uuid

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base


class ReportType(str, enum.Enum):
    blowdown = "blowdown"
    trash = "trash"
    bad_hikers = "bad_hikers"
    flooding = "flooding"
    shelter_repair = "shelter_repair"
    animals = "animals"
    # Problem plants or animals disrupting the local environment
    # (../../../features/REPORT_A_PROBLEM.md, 2026-07-30). Deliberately
    # separate from `animals`, which is scoped to SAFETY encounters and is
    # what HIKER_SAFETY.md escalates to severity=serious. An invasive report
    # is an ecological observation with no personal-risk dimension; folding
    # the two together would either dilute the safety signal or treat a plant
    # sighting as a hazard.
    invasive_species = "invasive_species"
    # A comment about a specific place, not a condition report - see
    # ../../../features/SAYING_THANKS.md. Shares every field; diverges in
    # visibility (club_only), states, and in skipping the moderation queue.
    thanks = "thanks"


class ReporterType(str, enum.Enum):
    thru = "thru"
    section = "section"
    day = "day"
    maintainer = "maintainer"


class ReportStatus(str, enum.Enum):
    submitted = "submitted"
    verified = "verified"
    resolved = "resolved"
    dismissed = "dismissed"


class Visibility(str, enum.Enum):
    public = "public"
    # Goes to safety moderators. Named for the bad_hikers case.
    internal_only = "internal_only"
    # Goes to the club and the maintainer - a different audience, for a
    # different reason (morale, not risk). Kept distinct from internal_only
    # so "who can see this" never depends on also reading the type.
    club_only = "club_only"


class Severity(str, enum.Enum):
    normal = "normal"
    serious = "serious"


class Report(Base):
    __tablename__ = "reports"

    # A Python-generated UUID string primary key, not a DB-generated
    # integer one - the same shape Profile.id already uses (see profile.py,
    # where the id is Supabase's `auth.users` id and so is not this
    # database's to mint). Reports keep it because a client can name its own
    # id before the row exists, which is what makes the idempotent retry in
    # routers/reports.py possible at all.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    reporter_id = Column(String, ForeignKey("profiles.id"), nullable=False)

    # native_enum=False, matching Profile.role's exact pattern - see
    # profile.py for why a native enum is the harder one to change later,
    # and for what this really renders as on Postgres (a bare VARCHAR: the
    # values are enforced in Python, not by the database).
    type = Column(Enum(ReportType, native_enum=False, length=20), nullable=False)

    # Location reference: either poi_id (a soft reference, see module
    # docstring) or a dropped/GPS pin (lat/lon) - never both required,
    # neither enforced exclusive here since v1 doesn't need that rule
    # policed server-side yet.
    poi_id = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    reporter_type = Column(Enum(ReporterType, native_enum=False, length=20), nullable=False)

    # When the report was WRITTEN. WIREFRAMES.md is explicit that this is
    # "the moment of writing, not of sending" - a report composed offline on
    # Monday and synced on Thursday must read as Monday, or a maintainer
    # mis-prioritises it and a `bad_hikers` timeline is distorted. The client
    # supplies it via `ReportCreate.authored_at`; the server falls back to now
    # when it is absent, and refuses a future-dated claim outright.
    timestamp = Column(DateTime, nullable=False, default=utc_now)

    # When the server actually received it - always server truth, never the
    # client's claim. Keeping both is what lets a genuinely three-day-old
    # report be told apart from a backdated one.
    received_at = Column(DateTime, nullable=False, default=utc_now)

    note = Column(Text, nullable=True)
    photo_url = Column(String, nullable=True)

    # Structured, type-specific follow-up fields (species/count for
    # animals, depth for flooding, etc.) - always empty in v1 (see
    # REPORT_A_PROBLEM.md's "Follow-up info, phased" section); the column
    # exists now so it can be populated later without a schema rewrite.
    follow_up = Column(JSON, nullable=True)

    status = Column(Enum(ReportStatus, native_enum=False, length=20), nullable=False, default=ReportStatus.submitted)

    # Server-controlled from `type` alone - see module docstring. No
    # column-level default: the router always computes and sets this
    # explicitly rather than relying on an implicit fallback.
    visibility = Column(Enum(Visibility, native_enum=False, length=20), nullable=False)

    # Server-controlled; only a later verify action (another task) can
    # raise this to `serious` - no field on the create schema at all.
    severity = Column(Enum(Severity, native_enum=False, length=20), nullable=False, default=Severity.normal)

    # Optional attribution for a `thanks` (SAYING_THANKS.md). Both may be
    # empty: "someone cleared forty blowdowns and I have no idea who" is a
    # complete thanks, resolved by location instead of being refused.
    maintainer_id = Column(String, ForeignKey("profiles.id"), nullable=True)
    club_id = Column(String, ForeignKey("clubs.id"), nullable=True)
