"""Resolving "who looks after this spot?" from a location and a date.

See ../../../features/SAYING_THANKS.md and VOLUNTEERING.md's
`MaintainerAssignment` section.

No auth: this is a browsing endpoint like every other read in the app.

The `as_of` parameter is the point of the whole versioned model. A thanks
written in June, about a section reassigned in July, syncing from an outbox
in August has to resolve to the JUNE maintainer - so callers pass the
report's authored date, not today's. It defaults to today only for the
plain "who has this now?" case.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.assignments import assignments_covering
from app.db.session import get_db
from app.schemas.maintainer_assignment import MaintainerAssignmentOut

router = APIRouter(tags=["maintainer-assignments"])


@router.get("/maintainer-assignments", response_model=list[MaintainerAssignmentOut])
def resolve_assignments(
    mile: float = Query(..., description="Position along the centerline, in miles."),
    as_of: date | None = Query(
        None,
        description="Resolve against this date rather than today - pass a report's authored date.",
    ),
    db: Session = Depends(get_db),
) -> list[MaintainerAssignmentOut]:
    """Every assignment covering `mile` on `as_of`.

    Returns zero or more, never exactly one: stretches overlap at
    boundaries, hand off mid-season, and go unassigned when a volunteer
    steps back. Zero is a normal answer - the caller falls back to the club
    or simply keeps the location.

    **The query itself moved to app/core/assignments.py** (#249), because
    receiving a thanks and delivering one now ask the same question. This is
    the only caller allowed to default `as_of` to today - see that module.
    """
    rows = assignments_covering(db, mile, as_of or date.today())

    return [
        MaintainerAssignmentOut(
            id=assignment.id,
            club_id=assignment.club_id,
            club_name=club.name,
            # Opt-in only. Withheld by default rather than filtered out
            # downstream, so a caller cannot leak it by forgetting to check.
            display_name=profile.display_name if assignment.publicly_creditable else None,
            start_mile=assignment.start_mile,
            end_mile=assignment.end_mile,
            effective_from=assignment.effective_from,
            effective_to=assignment.effective_to,
        )
        for assignment, club, profile in rows
    ]
