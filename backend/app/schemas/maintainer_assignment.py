"""Response models for maintainer-assignment resolution.

`display_name` is deliberately nullable and deliberately computed rather
than joined blindly: it is populated only when the assignment is marked
`publicly_creditable`. See ../../../features/SAYING_THANKS.md - individual
attribution is opt-in, club attribution is the default.
"""

from datetime import date

from pydantic import BaseModel


class MaintainerAssignmentOut(BaseModel):
    id: str
    maintainer_id: str
    club_id: str
    club_name: str
    # None unless this maintainer opted in to being publicly creditable.
    display_name: str | None
    start_mile: float
    end_mile: float
    effective_from: date
    effective_to: date | None
