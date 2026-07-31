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
    # app/models/report.py's module docstring for why (sidesteps the
    # SERIAL-on-DuckDB gap backend/README.md documents).
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
    status = Column(Enum(ClosureStatus, native_enum=False, length=20), nullable=False, default=ClosureStatus.open)

    # Whether this closure has been through moderation yet - see module
    # docstring. Never client-settable on create; only PATCH (role-gated to
    # maintainer/club_admin) can move it.
    moderation_status = Column(
        Enum(ModerationStatus, native_enum=False, length=20), nullable=False, default=ModerationStatus.submitted
    )

    verified_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
