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

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.club import Club
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.profile import Profile


def stood_behind() -> ColumnElement[bool]:
    """The assignments a hiker-facing read may believe. Needs `Club` joined.

    #1635 - The organization console's new endpoints trust self-registered
    orgs with maintainer powers, seats and mail. Until it, every row in
    `maintainer_assignments` carried the same weight here, and the console
    made that unsafe: `POST /clubs` makes anybody whose verified address is at
    the domain they typed a claimed org's approved admin, and that admin could
    then write an assignment over any miles. One note from a "covering
    maintainer" marks a spring missing on the map (`core/disputes.py`), and a
    covering assignment receives other hikers' private thanks.

    So a row counts for hikers when something other than the organization
    itself stands behind it. Two things do, today:

    - **A maintainer loaded it from a reviewed file** (`load_assignments.py`).
      Those rows carry neither stamp: the loader writes no `proposed_by` and
      no `confirmed_by`, and every console write since #1635 carries one or
      the other (`routers/org_roles.py`; `test_org_console_authz.py` pins
      the sync case, the one that used to write neither).
    - **An admin confirmed it at an organization a maintainer wrote**, which
      is a club row with no `created_by` - the loader's clubs, and
      `pipeline/sources.json`'s. `register_org`, `claim_org` and nominating
      all set `created_by`, so no self-service path produces one.

    **Never an unconfirmed proposal**, which is a supervisor's suggestion
    waiting for an admin and was being counted as if it were the answer.

    **What this costs, stated rather than hidden:** an organization that
    registered or claimed itself through the console gives its volunteers no
    weight with hikers until a maintainer puts the same stretch through the
    reviewed file. That is the fail-closed direction, and a console-side way
    for a maintainer to vouch for an organization is follow-up work nobody
    has designed yet - the file is the one vouching path that exists.
    """
    loaded_from_a_file = and_(
        MaintainerAssignment.proposed_by.is_(None),
        MaintainerAssignment.confirmed_by.is_(None),
    )
    confirmed_at_a_maintainer_written_org = and_(
        MaintainerAssignment.confirmed_at.isnot(None),
        Club.created_by.is_(None),
    )
    return or_(loaded_from_a_file, confirmed_at_a_maintainer_written_org)


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
            stood_behind(),
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
