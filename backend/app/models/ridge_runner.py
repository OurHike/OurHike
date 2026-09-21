"""A volunteer trail monitor's commitment window - seven days, self-closing.

See ../../../features/VOLUNTEERING.md §3 and #763. **"Ridge Runner At-Large"
is the in-app name for the person who opted into it; anything an
organization or a third party sees reads "volunteer trail monitor"**, which
is the doc's own recommendation and #763's 2026-08-25 split. The reason is a
safety one rather than a branding one: "Ridge Runner" is ATC's own programme
name, and a hiker who believes they are talking to an ATC Ridgerunner may
take instructions - about a closure, a fire, where to camp - from a
volunteer with no authority to give them. The `blocked-external` label on
#763 is attached to the unqualified name reaching a third party, and it
stays on.

**The seven-day cap is the whole guardrail, and it is enforced here as well
as in the schema.** VOLUNTEERING.md:

    It is the closest thing to a streak this app will ever have - and the
    seven-day cap is what keeps it from being one. A commitment that ends
    cannot become an obligation that accumulates.

So there is no renewal prompt, no chain to break, and **no column anywhere
recording what was expected.** The record shows what was submitted, never
what was missed. A partial week is a week's worth of real work. If a future
change makes the window extendable, that paragraph is the thing it has to
argue against.

**The app issues nothing that functions as a badge.** No shareable card, no
title on a public profile, no on-map presence marking where somebody is. The
role is a mode the app is in, visible to its user and to the organization
receiving the data, and to nobody else - which is why this table has no
public read anywhere.

Submissions are ordinary `Report`s and field notes tagged with this id; there
is no new submission model, because this is a lens over machinery that
already exists (`trash` and `invasive_species` are already in the client
outbox's draft union).
"""

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base

# The cap, in days, counted inclusively: a window that starts and ends on the
# same day is one day, and the longest legal window is seven.
#
# Not @unvalidated - it is a design decision with its reasoning written down
# in VOLUNTEERING.md §3 rather than a number anybody measured, and the thing
# that would change it is an argument, not data.
MAX_COMMITMENT_DAYS = 7

# The tasks somebody can elect to do while the window is open. They filter
# what the app asks about; they are not a qualification and nothing checks
# one.
COMMITMENT_TASKS: tuple[str, ...] = ("cleanup_packout", "invasive_species", "trail_clearance")


class RidgeRunnerCommitment(Base):
    __tablename__ = "ridge_runner_commitments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    person_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)

    # Comma-separated members of COMMITMENT_TASKS. A join table for three
    # values on a row nobody queries by task would be ceremony; the schema
    # validates membership on the way in.
    tasks = Column(String, nullable=False, default="")

    # Resolved from MaintainerAssignment where the hiker does not know whose
    # section it is, which is the common case for somebody who simply walks a
    # lot. Null is fine and stays fine.
    club_id = Column(String, ForeignKey("clubs.id"), nullable=True)

    note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)

    # Set when the volunteer closes the window early. There is deliberately
    # no "completed" state and no completion percentage: the window ending is
    # not an outcome to be graded.
    ended_early_at = Column(DateTime, nullable=True)
