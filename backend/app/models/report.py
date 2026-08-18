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
    # Load-bearing and, today, unreachable (#257): the public-visibility rule
    # deliberately keeps resolved reports visible ("it reads as 'Fixed'",
    # routers/reports.py) and the client maps it (lib/reportStatus.ts), but no
    # endpoint sets it - the lifecycle dead-ends at verified/dismissed. The
    # resolve action belongs to the moderator surface (#235); until that
    # lands, "Fixed" is a state the vocabulary holds open rather than one a
    # report can wear.
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

    # index=True on the columns every hot query filters on (#658,
    # a1b7c3d95e04): the public list scans status, "my reports" scans
    # reporter_id. Cheap while the tables are small, which is exactly
    # when adding them is a one-line decision instead of an incident.
    reporter_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

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

    # Where along the centerline, in miles from the southern terminus (#244).
    #
    # **Client-supplied, and derived rather than measured** - the report form
    # snaps the GPS fix to the trail index it already holds and has been
    # computing this value, showing it ("mi 1,407.2"), and then dropping it at
    # submit. Same trust posture as `authored_at`: a claim, bounded at the one
    # end that can be bounded (see ReportCreate), with the server's own
    # `lat`/`lon` alongside it.
    #
    # **Nullable, and null is the ordinary state rather than a gap.** There is
    # no mile when the fix is off-trail, when the trail index has not been
    # downloaded yet, or for every row filed before this column existed. A
    # zero would be Springer Mountain, which is why it is not the default.
    #
    # Nothing server-side derives it, and nothing can: this backend holds no
    # centerline geometry - the trail is a published artifact the client and
    # the pipeline share, not a table here. That is why carrying it costs a
    # column rather than a function.
    mile = Column(Float, nullable=True)

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

    status = Column(
        Enum(ReportStatus, native_enum=False, length=20),
        nullable=False,
        default=ReportStatus.submitted,
        index=True,
    )

    # Server-controlled from `type` alone - see module docstring. No
    # column-level default: the router always computes and sets this
    # explicitly rather than relying on an implicit fallback.
    visibility = Column(Enum(Visibility, native_enum=False, length=20), nullable=False)

    # Server-controlled; only the verify action can raise this to `serious`
    # - no field on the create schema at all. That action leaves it ALONE
    # when a moderator says nothing about it, which it did not always do:
    # see app/schemas/moderation.py's ReportVerifyRequest for what a silent
    # de-escalation cost (#251).
    severity = Column(Enum(Severity, native_enum=False, length=20), nullable=False, default=Severity.normal)

    # Who moderated this, and when. The same pair `closure` has carried from
    # the start, added here because it was missing on the resource where the
    # question matters most: a `bad_hikers` report names a person, and "who
    # decided this was serious" had no answer at all.
    #
    # Nullable because most reports have never been through moderation -
    # `status` starts at `submitted` and a great many stay there. Null means
    # "nobody has verified this", which is exactly what `status` already
    # says; these two answer WHO and WHEN, not WHETHER.
    #
    # Deliberately NOT on the public `ReportOut`. Surfacing an audit trail is
    # the moderation surface's job (#235), and putting a moderator's profile
    # id into the anonymous `GET /reports` payload would walk straight into
    # the leak #252 is already open about.
    verified_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # The other two thirds of the moderation trail (#658, f2c8d4a91e57).
    # verified_* records the FIRST escalation and is never overwritten - who
    # first marked a dangerous-person report serious is the fact an audit
    # needs. dismissed_* records the LATEST removal - "who took this down"
    # means the operative decision. resolved_* records who declared the
    # hazard cleared, which is what finally makes ReportStatus.resolved
    # reachable rather than a state the vocabulary held open.
    dismissed_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Optional attribution for a `thanks` (SAYING_THANKS.md). Both may be
    # empty: "someone cleared forty blowdowns and I have no idea who" is a
    # complete thanks, resolved by location instead of being refused.
    maintainer_id = Column(String, ForeignKey("profiles.id"), nullable=True)
    club_id = Column(String, ForeignKey("clubs.id"), nullable=True)
