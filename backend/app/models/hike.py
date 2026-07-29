"""The `hikes` table - the minimal slice of SEGMENTS.md's `Hike` model that
../../../features/HIKER_SAFETY.md section 5's wrong-way/off-trail alert
depends on.

SEGMENTS.md's full `Hike`/`Segment` tree (day-by-day planning, completion
tracking, client-side IndexedDB storage) is Post-MVP - this table is
deliberately not that. It exists only so the wrong-way alert has a durable
overall start/end reference to read a hiker's intended direction of travel
from, matching that section's own framing: "no new state needed... just
reading what Segments already has."

`trail_id` is a plain string defaulting to "AT", not a foreign key to a
`Trail` table - multi-trail support stays Post-MVP (SEGMENTS.md's
"Inheritability check" section), so a real trails table would be premature
here.

**No `direction` column, deliberately.** Whether a hike is NOBO or SOBO is
fully determined by comparing `overall_start_reference` to
`overall_end_reference` - storing a separate `direction` value would just be
a second source of truth that could drift from the references it's derived
from. See `app/core/hike_direction.py`.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, String

from app.db.base import Base


class Hike(Base):
    __tablename__ = "hikes"

    # An app-generated UUID string primary key, not a DB-generated
    # autoincrement integer - sidesteps the same duckdb-engine "SERIAL does
    # not exist" gap backend/README.md documents (SQLAlchemy's default
    # "auto" autoincrement on an Integer primary key renders Postgres-only
    # `SERIAL` DDL that DuckDB's compiler doesn't support), and is portable
    # to Postgres too since the value is generated in Python either way.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(String, ForeignKey("profiles.id"), nullable=False)

    # Deliberate MVP minimalism (not a `Trail` table/foreign key) - see the
    # module docstring above.
    trail_id = Column(String, nullable=False, default="AT")

    # Mile-marker references along the trail centerline (e.g. 0.0 for
    # Springer, 2189.0 for Katahdin) - whichever is numerically larger
    # determines the hike's direction; see app/core/hike_direction.py.
    overall_start_reference = Column(Float, nullable=False)
    overall_end_reference = Column(Float, nullable=False)

    planned_start_date = Column(Date, nullable=True)

    # Naive UTC, matching app/models/profile.py's exact pattern - see that
    # module's docstring for why (duckdb-engine can't marshal TIMESTAMPTZ
    # back out without the optional pytz package).
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
