"""Workdays an organization runs, and the hands people put up for them.

See ../../../features/VOLUNTEERING.md §2 and §6, ../../../features/ORG_ONBOARDING.md,
and #762 (phase D) and #763 (phase E).

**A signup is an introduction, not an enrolment, and this model is where
that either holds or quietly stops holding.** VOLUNTEERING.md:

    A club workday is not an app event. Real ones carry waivers, minimum
    ages, tool-use training, and ATC volunteer registration; some are
    crew-lead-approved rather than open. The app must never leave someone
    believing they are on a roster when they are not.

So `confirmed` is set **by the organization**, never by this app, and the
state a volunteer sees is the organization's own reply rather than a green
tick of our invention. There is deliberately no path that sets `confirmed`
as a side effect of anything.

**Both signup paths are first-class, and that is the hard part.** An
organization with a working calendar is not going to abandon it. A
`mirrored` project is authoritative on their own system and its signup goes
to *their* form; an `ourhike` one uses ours. The screen says which, in as
many words, rather than rendering a button that quietly does something else.

**Nothing here notifies anybody.** OurHike sends no push notification of any
kind, and per value #9's own warnings there is no broadcasting of large
gatherings and nothing that turns a workday into an event to be amplified.
Small, well-timed and local is the whole point.

**Why this table can be written self-service when the registry cannot.**
SOURCE_REGISTRY.md's rule is that nothing self-service changes a hiker's map
without a merge. ORG_ONBOARDING.md relaxes it here, explicitly, for this data
class and only this one: a workday carries no geometry a hiker navigates by,
and a wrong one costs somebody a Saturday rather than a wrong turn. That is
a different risk class from a trail line. #763 asked for that decision to be
stated before the module was built rather than discovered during it.
"""

import enum
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.core.time import utc_now
from app.db.base import Base


class ProjectStatus(str, enum.Enum):
    upcoming = "upcoming"
    completed = "completed"
    cancelled = "cancelled"


class SignupMode(str, enum.Enum):
    """Where a signup actually goes.

    Matches `pipeline/lib/work_projects.py`'s `SIGNUP_MODES`, which refused
    `in_app` by name until this backend existed - "a row claiming it before
    the endpoint exists would render a button that files nothing." It exists
    now, and that tuple widens in the same change.
    """

    contact = "contact"
    in_app = "in_app"


class ProjectSource(str, enum.Enum):
    ourhike = "ourhike"
    mirrored = "mirrored"


class SignupState(str, enum.Enum):
    """VOLUNTEERING.md's four, plus the volunteer's own way out.

    `cancelled_by_volunteer` is one tap and utterly consequence-free, which
    is #762's open question answered the way that issue's own instinct
    pointed: a no-show costs an org a crew slot, and the alternative
    mitigation is tracking reliability, which is a reputation score the
    feature's rule 1 rules out. **Nothing anywhere counts how often somebody
    has been in this state**, and that absence is the design.
    """

    interested = "interested"
    confirmed = "confirmed"
    waitlisted = "waitlisted"
    declined = "declined"
    cancelled_by_volunteer = "cancelled_by_volunteer"


class WorkProject(Base):
    __tablename__ = "work_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # A date range covers the single-day case and the weekend one.
    # Recurrence is deliberately not modelled: "every third Saturday" needs
    # real structure and should be decided from what organizations actually
    # run, not guessed at (VOLUNTEERING.md's open questions).
    starts_on = Column(Date, nullable=False, index=True)
    ends_on = Column(Date, nullable=False)

    # Where to meet, in the org's own words - "Reeves Meadow Visitor
    # Center, 8am". Free text on purpose: this is an instruction to a human
    # standing in a car park, not a point anything routes to.
    meet_point = Column(String, nullable=True)

    # Roughly where the work is, for the map pins. Nullable because plenty
    # of workdays are "somewhere on the Ramapo-Dunderberg" until the day.
    mile = Column(Float, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    status = Column(
        Enum(ProjectStatus, native_enum=False, length=20),
        nullable=False,
        default=ProjectStatus.upcoming,
    )

    # Null means "no cap stated", not "unlimited" and not "zero". An org that
    # has not said is a different thing from one that said everybody is
    # welcome, and the screen renders the two differently.
    cap = Column(Integer, nullable=True)

    source = Column(
        Enum(ProjectSource, native_enum=False, length=20),
        nullable=False,
        default=ProjectSource.ourhike,
    )
    signup_mode = Column(
        Enum(SignupMode, native_enum=False, length=20),
        nullable=False,
        default=SignupMode.in_app,
    )
    # Where a `contact` signup goes - a mailto or a phone number - or, for a
    # mirrored project, the org's own signup form.
    signup_contact = Column(String, nullable=True)
    signup_url = Column(String, nullable=True)

    created_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class WorkProjectSignup(Base):
    """One person putting their hand up, and the organization's own reply."""

    __tablename__ = "work_project_signups"
    __table_args__ = (UniqueConstraint("work_project_id", "person_id", name="uq_work_project_signups_project_person"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    work_project_id = Column(String, ForeignKey("work_projects.id"), nullable=False, index=True)
    person_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

    state = Column(
        Enum(SignupState, native_enum=False, length=30),
        nullable=False,
        default=SignupState.interested,
    )

    # What the volunteer said when they signed up - "I have a saw
    # certification" - and what the org said back. The reply message is the
    # part that makes the answer the organization's own rather than the
    # app's, so it travels with the state wherever the state is shown.
    note = Column(Text, nullable=True)
    reply_message = Column(Text, nullable=True)

    # Who answered, and when. A supervisor or an admin, never the app.
    replied_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    replied_at = Column(DateTime, nullable=True)

    # Set after the fact, and it pre-fills an hours claim rather than
    # creating one - hours are claimed, not computed, and somebody who turned
    # up and worked four hours is the one who knows it was four.
    attended = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
