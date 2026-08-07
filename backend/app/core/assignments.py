"""Who looks after a point on the trail, on a given date - asked once.

See ../../../features/SAYING_THANKS.md ("Resolving 'who do I thank?' by
location") and VOLUNTEERING.md's `MaintainerAssignment` section.

**This module exists because the same question is now asked from three
places** (#249), and before it did they were one implementation and two
promises. `GET /maintainer-assignments` answered it for the form's preview.
`create_report` claimed to answer it when a thanks arrived - the client says
so in `lib/maintainerLookup.ts`, in as many words - and did not. And nothing
at all answered "which thanks should this maintainer see", so a thanks was
readable by exactly one person forever: its author.

Three callers and one query, because the alternative is the failure this
codebase has already had once with `_visible_to`: a rule written twice,
drifting, and the drift only visible in the case nobody tests. Here that case
is a volunteer being credited for someone else's stretch, or not being
credited at all.

WHY `as_of` IS NOT OPTIONAL HERE

The router's parameter defaults to today, which is right for the browsing
question ("who has this now?"). Nothing else may default it. A thanks written
in June about a section reassigned in July and synced in August belongs to
the JUNE maintainer, and every caller that stores or delivers one has an
authored date to pass. Making the argument required is what stops "now" from
being reached for by accident at the one call site where it is wrong.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import Profile


def assignments_covering(db: Session, mile: float, when: date) -> list[tuple[MaintainerAssignment, Club, Profile]]:
    """Every assignment covering `mile` on `when`, with its club and person.

    **Zero or more, never exactly one**, and that is the model rather than a
    caveat (SAYING_THANKS.md). Stretches overlap at boundaries, hand off
    mid-season, and go unassigned when a volunteer steps back. Zero is a
    normal answer - the caller falls back to the club or simply keeps the
    location. Two is normal too, and both hear about it.

    Joined rather than left-joined on purpose: an assignment whose club or
    maintainer row is missing is a broken row, and answering "who looks after
    this" with a half-resolved one would put a null where a name goes.
    """
    return (
        db.query(MaintainerAssignment, Club, Profile)
        .join(Club, Club.id == MaintainerAssignment.club_id)
        .join(Profile, Profile.id == MaintainerAssignment.maintainer_id)
        .filter(
            MaintainerAssignment.start_mile <= mile,
            MaintainerAssignment.end_mile >= mile,
            MaintainerAssignment.effective_from <= when,
            or_(
                MaintainerAssignment.effective_to.is_(None),
                MaintainerAssignment.effective_to >= when,
            ),
        )
        .all()
    )
