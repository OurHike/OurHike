"""The `volunteer_hours` table - self-logged, club-confirmed volunteer work.

See ../../../features/VOLUNTEERING.md §4 and #761. Two states plus a removal
carry the whole design: a record is `claimed` the moment its volunteer files
it, `confirmed` once a club admin stands behind it, and `disputed` when one
refuses to - and the distinction exists because these numbers have an
external consumer with real weight: clubs report volunteer hours upward, to
ATC and to the land-managing agencies, where they figure in funding.

**What `claimed` counts for is decided, not drifted into** (the issue's own
ask): maintainer decision 2026-08-20, in session, recorded on #761 - claimed
hours count everywhere immediately, the fee exemption included, until a club
disputes them; confirmation upgrades the state and a dispute removes the
record from every total. The state is always labeled wherever an hour is
shown or exported, so a reader can always tell a claim from a grant. This
supersedes PRICING_MODEL.md's "grant, don't self-report" posture for the
exemption, and that doc's record is updated in the same change.

Hours are **claimed, not computed** - the app could infer them from GPS and
would be wrong constantly (a lunch break, a drive to the trailhead, a phone
in a pack all day). Ask the person; they know.

`work_project_id` is a soft string reference into the published
conditions/work_projects.json rows, report.py's poi_id precedent exactly:
workdays live in a reviewed file (and later in club tooling), not in a table
here, so there is nothing for a real FK to point at. Null is the COMMON
case, not a gap - most maintenance is somebody going out on a Tuesday
because a blowdown needs clearing, and a design that only counted organised
workdays would miss the majority of the work it is trying to honour.

`club_id` is nullable where VOLUNTEERING.md's sketch drew it required, and
the divergence is deliberate: a hiker who cleared a blowdown often does not
know whose section it was, and refusing the record until they find out
would lose the hour. RidgeRunnerCommitment's sketch already makes the same
call for the same reason ("resolved from MaintainerAssignment where the
hiker does not know"). A record with no club can still be confirmed later
by whoever claims the stretch - Phase D's problem, not this row's.

See app/models/profile.py for the naive-UTC convention.
"""

import enum
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, Float, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base


class HoursActivity(str, enum.Enum):
    maintenance = "maintenance"
    cleanup = "cleanup"
    monitoring = "monitoring"
    education = "education"
    admin = "admin"
    other = "other"


class HoursState(str, enum.Enum):
    claimed = "claimed"
    confirmed = "confirmed"
    disputed = "disputed"


class VolunteerHoursRecord(Base):
    __tablename__ = "volunteer_hours"

    # Client-minted UUID string - the outbox idempotency shape every other
    # submitted record uses (see report.py's id comment).
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # "my hours" is the hot query - the dashboard reads it on every open.
    user_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
    club_id = Column(String, ForeignKey("clubs.id"), nullable=True)

    worked_on = Column(Date, nullable=False)
    hours = Column(Float, nullable=False)

    work_project_id = Column(String, nullable=True)
    activity = Column(Enum(HoursActivity, native_enum=False, length=20), nullable=False)
    # In the volunteer's own words, optional - "cleared four blowdowns south
    # of the gap". The record is theirs first (a logbook, VOLUNTEERING.md
    # §5); the words are for them, and for the club admin deciding whether
    # to stand behind the number.
    note = Column(Text, nullable=True)

    # Roughly where, as a mile and/or a point - all nullable, because "I
    # don't remember exactly" must not lose the hour.
    mile = Column(Float, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    state = Column(
        Enum(HoursState, native_enum=False, length=20),
        nullable=False,
        default=HoursState.claimed,
    )

    # Who stood behind it (or refused to), and when - the audit pair every
    # moderated resource here carries. A club admin, never the volunteer.
    confirmed_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)

    # When the record reached this server - server truth. `worked_on` is the
    # volunteer's claim about the day, and days are the honest precision for
    # trail work (nobody clocks in at a blowdown).
    recorded_at = Column(DateTime, nullable=False, default=utc_now)
