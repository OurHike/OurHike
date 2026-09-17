"""The three tiers an organization's trails arrive in: park, trail, section.

See ../../../features/ORG_ONBOARDING.md's data model, and #1540. This is what
the hike registry writes and what registry sign-off publishes - not directly,
because **nothing here reaches a hiker without a merged pull request.** These
rows are the org's proposal in a form the console can show them; the bytes on
a phone still come out of `pipeline/export_club_sections.py` after a person
merges. SOURCE_REGISTRY.md's rule survives self-service, and this is the table
it survives in.

**Why three tiers and not one.** ATC has one trail with many sections;
NYNJTC has many systems, each with many trails. A single flat list can
describe the first and not the second, and a two-tier model asks ATC to
invent a park it does not have. So the top tier is allowed to be **thin
without being wrong** - an org with one park has one row - which is a
cheaper failure than asking every organization to invent a hierarchy.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base


class ParkKind(str, enum.Enum):
    park = "park"
    system = "system"
    forest = "forest"


class OrgPark(Base):
    """Top tier - a park, a trail system, or a forest.

    Named `OrgPark` rather than `Park` because "park" is a word this codebase
    already uses for a place a hiker walks in (`pipeline`'s park polygons,
    the download window's named places). This one is an organizational
    grouping that usually coincides with one and is not required to.
    """

    __tablename__ = "org_parks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    kind = Column(Enum(ParkKind, native_enum=False, length=20), nullable=False, default=ParkKind.park)

    created_at = Column(DateTime, nullable=False, default=utc_now)


class OrgTrail(Base):
    """Middle tier - one named line, or one unnamed one.

    **A trail with no name and no blaze is legitimate**, which is why both
    columns are nullable and neither has a default. It is a route on a map,
    and organizations publish them. Anything that required a name here would
    get a fake one, and a fake name is worse than an absent one because it
    reads as a fact.

    **The two blaze columns are not redundant.** `blaze_value_raw` keeps the
    organization's own string exactly as their GIS spells it - "Red on
    white", "R/W", "#b3312c", whatever is actually in the column.
    `blaze_mapped` is the one of ours it maps onto, and **the mapping is
    theirs to confirm rather than ours to assume**: a blaze colour in a map
    or a table is data, not decoration, and guessing one wrong puts a hiker
    at the wrong junction. Keeping the raw string means a mapping can be
    corrected later without going back to the source.
    See ../../../features/TRAIL_BLAZE_COLORS.md for what we can render.
    """

    __tablename__ = "org_trails"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    park_id = Column(String, ForeignKey("org_parks.id"), nullable=False, index=True)

    name = Column(String, nullable=True)
    blaze_value_raw = Column(String, nullable=True)
    blaze_mapped = Column(String, nullable=True)
    miles = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)


class OrgSection(Base):
    """Bottom tier - the stretch one volunteer looks after.

    **Anchors reference mile markers or POIs, never free text.** SEGMENTS.md
    already specifies this and VOLUNTEERING.md repeats it, for one reason
    that is easy to under-weight until it bites: a report filed three weeks
    ago has to route to whoever covered that mile *then*. "From the big oak
    to the second stream crossing" cannot be resolved by a lookup, so an
    anchor that is free text is an anchor that quietly stops working the
    first time a section changes hands.

    The anchors are stored here as their resolved position along the
    centerline (`start_mile`, `end_mile`), which is the form the lookup needs
    - the same normalisation `maintainer_assignments` already does, and for
    the same reason. `start_anchor`/`end_anchor` keep what the org called
    them so the console can show a person something they recognise.

    `geometry` is a GeoJSON LineString as text, nullable because a section
    can be described before it is drawn. It is deliberately not a PostGIS
    type: nothing in this backend does spatial maths, the pipeline is where
    geometry gets worked on, and adding an extension to carry a string would
    be a dependency bought for nothing.
    """

    __tablename__ = "org_sections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    trail_id = Column(String, ForeignKey("org_trails.id"), nullable=False, index=True)

    name = Column(String, nullable=False)

    start_anchor = Column(String, nullable=True)
    end_anchor = Column(String, nullable=True)
    start_mile = Column(Float, nullable=True)
    end_mile = Column(Float, nullable=True)
    miles = Column(Float, nullable=True)

    geometry = Column(Text, nullable=True)

    # Which of the org's own regions this sits in - a plain string, because
    # regions are the org's vocabulary and are used by the coverage report
    # only. Modelling them as a table would let a region be renamed centrally
    # and would also let one be deleted out from under a section; the
    # coverage report groups by this value and needs nothing more.
    region = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
