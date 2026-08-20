"""The `app_failures` table - a hiker telling us this software failed them
on the trail.

See ../../../features/APP_FAILURE_REPORTS.md, and #848. This is not a
`Report` (app/models/report.py) and the distinction is the whole reason it
is a second table rather than an eighth `ReportType`:

  - A `Report` is about the TRAIL. It is public by default, it carries a
    location and a mile so it can be drawn as a pin, and it goes through
    the moderation queue closures and warnings share.
  - An `AppFailure` is about THIS SOFTWARE. Nothing about it is ever drawn
    on a map, nobody moderates it, and it carries the one field a report
    must never carry: a way to contact the person who wrote it.

Folding the two together would have put `contact` on the model that
`ReportOut` serialises to anonymous callers, one forgotten field away from
the leak features/IDENTITY_AND_PRIVACY.md and #252 are about. Two tables
means that mistake is not available to make.

**Nothing serves this table.** There is no `GET` on
app/routers/app_failures.py, by design rather than by omission - a
maintainer reads these rows with psql. A row here holds an email address or
a phone number that somebody handed over while shaken, and the cheapest
guarantee that it is never served to the wrong caller is that it is never
served at all. Add a read endpoint only with an answer to "who may read a
stranger's phone number, and how is that checked".

Every datetime column follows the naive-UTC convention app/models/profile.py
documents.
"""

import enum
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base


class Harm(str, enum.Enum):
    """The four ways ../../../CLAUDE.md says this app can hurt somebody.

    Written down as a vocabulary rather than left to free text because it is
    the only part of this report a maintainer can sort a morning's inbox by.
    The words are CLAUDE.md's, narrowed to one token each: "Lost, out of
    water, in front of something dangerous, or unable to get off the trail
    quickly."

    Stored as a JSON list on the row rather than as one column each, because
    they arrive together, are read together, and nothing filters on a single
    one - the same reasoning app/models/preferences.py gives for its own
    JSON column.

    **A report naming none of these is ordinary, not incomplete.** The form
    asks; it does not require. Somebody who writes "the map went blank at
    the Fontana ford" and ticks nothing has told us the important half.
    """

    lost = "lost"
    water = "water"
    hazard = "hazard"
    stranded = "stranded"


class AppFailure(Base):
    __tablename__ = "app_failures"

    # A client-minted UUID string, same shape and same reason as `Report.id`:
    # the outbox names the id before the row exists, which is what makes the
    # resend in routers/app_failures.py idempotent rather than duplicating.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # **Nullable, and null is an ordinary state rather than a gap.** Every
    # other write in this backend requires an account; this one does not,
    # because requiring somebody to sign in before they can tell us the app
    # nearly got them lost gets the priority exactly backwards. Null means
    # the report arrived with no token, which is most of what we expect.
    #
    # Indexed because the one query a maintainer runs against this column is
    # "has this person written to us before", and it is cheap to add now.
    reporter_id = Column(String, ForeignKey("profiles.id"), nullable=True, index=True)

    # What broke. The only required field on the whole row: a report with
    # nothing in here is not a report, and everything else - where, contact,
    # harms - is a thing we would like and can do without.
    what_happened = Column(Text, nullable=False)

    # Where they were, in their own words: "mi 1,407", "the ford below
    # Fontana", "no idea, somewhere in the Whites". Deliberately free text
    # and deliberately not a GPS fix. lib/bugReport.ts already declines to
    # attach `navigator.userAgent` to a bug report on the ground that the
    # device "is a fact about them"; a location is a stronger one, and this
    # app does not take it silently to save somebody typing.
    whereabouts = Column(Text, nullable=True)

    # How to reach them, in whatever form they chose to give it - an email,
    # a phone number, a forum handle, "I'm at Standing Bear Friday". Not
    # parsed, not validated, not required. Anything that constrained the
    # shape would be a way of refusing a contact detail somebody offered,
    # which is the opposite of what this column is for.
    contact = Column(Text, nullable=True)

    # A list of `Harm` values, or null. See the enum above.
    harms = Column(JSON, nullable=True)

    # Which build failed, as the phone reported it (client/src/lib/
    # buildInfo.ts). A claim, like every client-supplied field here, and
    # worth having anyway: it is the difference between a bug we can go and
    # look at and one we can only sympathise with.
    build = Column(String, nullable=True)

    # Whether the phone thought it was offline when this was written.
    #
    # Attached by the client rather than asked, and it is the one fact worth
    # attaching: `.github/ISSUE_TEMPLATE/bug_report.yml` already asks for it
    # in words ("whether you had signal at the time"), and for this class of
    # failure it is nearly always the answer. Nullable so "the report did not
    # say" stays distinguishable from "it said no" - a false is a claim.
    #
    # **Asymmetrically reliable, and worth knowing before reading a row.**
    # `true` is trustworthy. `false` is `navigator.onLine` (client/src/lib/
    # useOnline.ts), which is optimistic by design - it reports a captive
    # portal, or a bar of signal that carries no data, as online. A `false`
    # here therefore means "the phone believed it had a connection", not
    # "a request would have succeeded".
    was_offline = Column(Boolean, nullable=True)

    # When it was WRITTEN, which for an offline-first app is not when it
    # arrived - the same pair `Report.timestamp`/`Report.received_at` keeps,
    # for the same reason. A failure written on a ridge on Monday and flushed
    # in town on Thursday is a Monday failure.
    #
    # Unlike `ReportCreate.authored_at`, a future-dated claim is NOT refused
    # here. See app/schemas/app_failure.py for why: a 422 on this endpoint
    # does not bounce a request, it strands the report permanently in the
    # sender's outbox, and a wrong phone clock is not a reason to lose the
    # one report this project should most want to receive.
    authored_at = Column(DateTime, nullable=False, default=utc_now)

    # Server truth, always. Keeping both is what lets a genuinely four-day-old
    # failure be told apart from one carrying a wrong clock.
    received_at = Column(DateTime, nullable=False, default=utc_now)

    # When somebody actually got back to them.
    #
    # **Nothing writes this yet, and that is stated rather than hidden.** No
    # endpoint sets it and no screen shows it; a maintainer who answers a
    # report stamps it by hand. It is here because the alternative is an
    # inbox with no way to tell an answered report from an unanswered one,
    # and this table's whole reason for existing is that somebody gets
    # answered. `ReportStatus.resolved` spent a release in the same
    # condition (app/models/report.py) - held open by the vocabulary before
    # anything could reach it - so the shape is precedented and so is saying
    # so out loud.
    answered_at = Column(DateTime, nullable=True)
