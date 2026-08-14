"""Response models for maintainer-assignment resolution.

`display_name` is deliberately nullable and deliberately computed rather
than joined blindly: it is populated only when the assignment is marked
`publicly_creditable`. See ../../../features/SAYING_THANKS.md - individual
attribution is opt-in, club attribution is the default.

There is deliberately no `maintainer_id` here (#641). It is a stable account
id, this endpoint needs no account, and a sweep of `?mile=` down the corridor
would have keyed every volunteer's stretch and schedule to a joinable UUID -
the same shape #252 removed from public reports and #430 from public
closures. Consent gates the *name*; nothing public carries the id at all.
Thanks resolution never needed it over HTTP: `assignments_covering` hands the
id to the server-side callers that credit a report.
"""

from datetime import date

from pydantic import BaseModel


class MaintainerAssignmentOut(BaseModel):
    id: str
    club_id: str
    club_name: str
    # None unless this maintainer opted in to being publicly creditable.
    display_name: str | None
    start_mile: float
    end_mile: float
    effective_from: date
    effective_to: date | None
