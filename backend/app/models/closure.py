"""The `closure` table - trail closures (storm damage, flooding, reroutes).

See ../../../features/MAP_OPTIONS.md's closures/reroutes section. A closure
is a line along the trail, not a pin - `start_mile_marker`/`end_mile_marker`
are a soft reference into the pipeline's static centerline export (see
app/models/report.py's module docstring for why `poi_id` there is a plain
string rather than a ForeignKey - the same reasoning applies here), not a
stored geometry.

`reason_type` + `note` is a deliberate split of MAP_OPTIONS.md's single
ambiguous "reason (storm damage, flooding... matching Report a Problem's
type + note shape)" bullet into a real enum + free text, actually mirroring
that stated analogy rather than leaving it as one untyped field.

`moderation_status` is a real gap: MAP_OPTIONS.md has no moderation-state
field at all, only `status` (the closure's *real-world* condition - open,
closed, or a reroute being available). Report a Problem's own architecture
note says nothing becomes visible to other hikers before moderation, and
MAP_OPTIONS.md says Closures reuse that exact same queue - but never gives
Closures a field to encode "has this been verified yet" the way Report's
`status`/`visibility` pair does. Added here, mirroring Report's shape:
public queries filter on `moderation_status == verified`, independent of
whatever the closure's real-world `status` is.

`OurHike does not compute detours` (MAP_OPTIONS.md, explicit) - there is no
routing/geometry field here, only reason/status/dates for a hiker to read.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base


class ReasonType(str, enum.Enum):
    storm_damage = "storm_damage"
    flooding = "flooding"
    maintenance = "maintenance"
    relocation = "relocation"
    other = "other"


class ClosureStatus(str, enum.Enum):
    open = "open"
    closed = "closed"
    reroute_available = "reroute_available"


class ModerationStatus(str, enum.Enum):
    submitted = "submitted"
    verified = "verified"
    dismissed = "dismissed"


class Closure(Base):
    __tablename__ = "closures"

    # App-generated UUID string PK, matching Report/Hike's pattern - see
    # app/models/report.py for why.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    reported_by = Column(String, ForeignKey("profiles.id"), nullable=False)
    reported_at = Column(DateTime, nullable=False, default=utc_now)

    # Deliberate MVP minimalism, not a Trail table - multi-trail stays
    # Post-MVP (see app/models/hike.py's identical pattern/reasoning).
    trail_id = Column(String, nullable=False, default="AT")

    start_mile_marker = Column(Float, nullable=False)
    end_mile_marker = Column(Float, nullable=False)

    reason_type = Column(Enum(ReasonType, native_enum=False, length=20), nullable=False)
    note = Column(Text, nullable=True)

    # The closure's real-world physical state.
    #
    # Born `closed`, and that default is load-bearing rather than arbitrary.
    # `open` here means REOPENED - the state a maintainer moves a closure to
    # when the trail is walkable again - and the client renders it as exactly
    # that: `closureBanner` stays silent ("a reopened closure is not a
    # warning") and ClosureSheet says "Open again".
    #
    # So while this defaulted to `open`, the designed happy path published a
    # nonsense record. Someone reports a closure because the trail is closed;
    # a moderator verifies it; and `GET /closures` served a verified closure
    # the client was contractually obliged to present as reopened trail, with
    # no banner and no band. Making it show meant a second, separate
    # `PATCH /closures/{id}` that no code path suggested and no test
    # exercised (#246).
    #
    # One word was doing two jobs - the enum's "reopened again" meaning and
    # the column's birth default. Only the second was ever wrong.
    #
    # A Python-side default rather than a `server_default`, matching the
    # column as the initial migration created it, so this needs no revision
    # of its own: SQLAlchemy applies it on every insert, and there is no
    # deployed database holding rows written under the old one (#95).
    status = Column(Enum(ClosureStatus, native_enum=False, length=20), nullable=False, default=ClosureStatus.closed)

    # Whether this closure has been through moderation yet - see module
    # docstring. Never client-settable on create; only PATCH (role-gated to
    # maintainer/club_admin) can move it.
    moderation_status = Column(
        Enum(ModerationStatus, native_enum=False, length=20), nullable=False, default=ModerationStatus.submitted
    )

    verified_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # The three fields the closure sheet renders that nothing could fill
    # (#245). All maintainer-set through `ClosureUpdate`, never accepted on
    # create, for the same reason `status` is not: reporting that a trail is
    # shut and judging when it reopens are different jobs.
    #
    # `closed_since` is when the TRAIL shut, which is neither `reported_at`
    # (when somebody filed it) nor `verified_at` (when a moderator confirmed
    # it). A closure reported four days after a storm is already four days old
    # when it arrives, and this is the field that says so.
    closed_since = Column(DateTime, nullable=True)

    # Null is not "unknown, ask later" - the client omits the line entirely
    # rather than rendering it, because "expected reopen: unknown" reads as a
    # promise nobody made.
    expected_reopen = Column(DateTime, nullable=True)

    # The club's own reroute notice, which is what the sheet's closing line
    # ("Follow the club's notice, or the signage on the ground") points at.
    # This is not OurHike computing a detour - the module docstring's
    # no-routing rule is about geometry we would have to derive, not about
    # linking to what the club already published. `ClosureStatus
    # .reroute_available` has existed since the initial schema; until this
    # column there was nowhere to say where the reroute actually is.
    #
    # Rendered as an outbound link, so the scheme is constrained to http/https
    # in app/schemas/closure.py rather than here: a `javascript:` URL on a
    # safety sheet is the reason that validation exists.
    reroute_url = Column(String, nullable=True)
