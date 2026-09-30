"""The `maintainer_assignments` table - who looks after which stretch, when.

See the `MaintainerAssignment` section of ../../../features/VOLUNTEERING.md.

Two design points carry the weight here:

**Assignments are versioned, not edited in place.** A mutable
`current_maintainer` field can answer "who has mile 1,043 today" and
destroys every other answer. The questions that actually matter are
historical - who cleared this in June, who should hear about a report
written three weeks ago - so an assignment has an `effective_from` and a
nullable `effective_to` (null meaning "current") and a hand-off closes one
row and opens another rather than overwriting anything.

**Position is stored as a mile range along the centerline.** SEGMENTS.md
allows a boundary to be a mile-marker point, a shelter/campsite/parking POI,
or a pin snapped onto real trail geometry - and all three normalise to a
position along the trail, which is exactly what a "who covers this spot?"
lookup needs. Storing the normalised form keeps the lookup a plain range
query with no geometry dependency; a richer reference (POI id + resolved
mile) can be added later without changing how resolution works.

`publicly_creditable` defaults to False on purpose - see SAYING_THANKS.md.
Maintainers are volunteers who often work a remote section alone on a
predictable schedule, so their name is only shown to hikers where the club
has their consent.
"""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, String

from app.db.base import Base


class MaintainerAssignment(Base):
    __tablename__ = "maintainer_assignments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Indexed (#658, a1b7c3d95e04): thanks delivery and the credit
    # resolution both look assignments up by who holds them.
    maintainer_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)

    # Inclusive range along the trail centerline, in miles from the southern
    # terminus - the same origin the pipeline's half-mile markers use.
    start_mile = Column(Float, nullable=False)
    end_mile = Column(Float, nullable=False)

    effective_from = Column(Date, nullable=False)
    # Null means "still current". Closing a row rather than deleting it is
    # what preserves the history this model exists for.
    effective_to = Column(Date, nullable=True)

    publicly_creditable = Column(Boolean, nullable=False, default=False)

    # WHAT THE ORG CONSOLE ADDED, 2026-09-17
    # (../../../features/ORG_ONBOARDING.md, and the model sketch there).
    #
    # Both nullable, and both stay nullable, because the file loader that
    # predates them writes neither: `load_assignments.py` takes a maintainer,
    # a club and a mile range from an organization's own records, and that is
    # still the right answer for one organization getting started. An
    # assignment made in the console carries the role it is an instance of and
    # the section it covers; one loaded from a file carries the miles alone.
    # Requiring either would break the loader to tidy a schema.
    #
    # `role_id` is what makes "who looks after this mile" answerable as "the
    # maintainer, supervised by Joseph" rather than just a name - which is the
    # question a report has to answer before it can be routed, and the reason
    # the coverage report can say a section has no role attached rather than
    # only that it has nobody on it.
    role_id = Column(String, ForeignKey("org_roles.id"), nullable=True, index=True)

    # The section this covers, where the org has drawn one. The mile range
    # above stays authoritative for resolution: it is what every existing
    # lookup queries, a section's own miles can be null while it is still
    # being described, and two sources of truth for one stretch is how a
    # report reaches the wrong person.
    section_id = Column(String, ForeignKey("org_sections.id"), nullable=True, index=True)

    # Set when the assignment was proposed by a supervisor and is waiting for
    # an admin to confirm it. ORG_ONBOARDING.md: supervisors propose, admins
    # confirm - because RLS says who may write, never whether a write was
    # right, and a wrong section assignment sends a hiker's report to the
    # wrong person. Null means it needs nobody's confirmation, which is what
    # an admin's own write and the file loader both produce.
    proposed_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    confirmed_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
