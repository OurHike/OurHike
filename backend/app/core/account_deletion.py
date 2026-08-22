"""Deleting an OurHike account: what goes, what stays, and why the line is there.

Phase E of ../../../features/ACCOUNT_SYNC.md (#895). Until phases A, B and D
landed, "delete my account" was a promise nobody needed us to keep: every
private thing a hiker owned lived on their own handset, so uninstalling *was*
deletion. Trips and preferences now sit on a server, so it stopped being true,
and the deal changed without anybody telling the hiker it had.

THE RULE, IN ONE SENTENCE

**A row goes if it was only ever the hiker's own; a row stays if somebody
else has already acted on it or is relying on it.** Everything below is that
sentence applied table by table, and each application is written down because
the reader who disagrees with one of them should be able to find the step
rather than the conclusion.

WHAT "STAYS, UNATTRIBUTED" ACTUALLY MEANS HERE

Not a null. `poi_photos` settles it: its R2 object key is derived from
`contributor_id` (core/photos.py `poi_photo_key`), so nulling that column
makes the photograph unreachable - deletion by another name, applied to the
one artifact carrying an irrevocable CC BY-SA 4.0 grant (#577). And
`uq_poi_photos_poi_contributor` means a single shared "deleted hiker" profile
would collide the moment two deleted accounts had photographed the same
shelter.

So the id survives and the person does not: `scrub_profile` empties the
`profiles` row of everything that says who it was, and core/auth.py refuses
to let the account be signed into again. A published row goes on pointing at
an account that belongs to nobody.

THE ONE THING THIS CANNOT DO, STATED RATHER THAN IMPLIED

**It does not delete the Supabase Auth user.** That needs a service-role key,
and app/config.py has none - only the anon key and the JWKS (core/auth.py).
So the email address and password hash Supabase holds are out of reach from
here, and a hiker who deletes their OurHike account still exists in Supabase
Auth until something with that key removes them. `deleted_at` plus the auth
guard is what stops that leftover credential being a way back in, which is
the part that would actually hurt somebody; the leftover row itself is a real
gap and is named in features/AUTHENTICATION.md rather than papered over.

WHAT IT DOES NOT TOUCH, DELIBERATELY

R2 objects belonging to rows that stay - a report's photo, a shared POI
photo. They are derived from rows this function is keeping, so sweeping them
would orphan a live row rather than tidy a dead one (core/photos.py: "the row
is authoritative, the object is derived"). Private photo backup is phase C
and is unbuilt, so there is no private object to sweep yet; ACCOUNT_SYNC.md's
"Decisions this document does not take" #3 - how long a deleted photo's
object survives in R2 - is still open and is a maintainer's call, not this
module's.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.app_failure import AppFailure
from app.models.closure import Closure
from app.models.field_note import FieldNote, NoteFlag
from app.models.hike import Hike
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.poi_photo import PoiPhoto
from app.models.preferences import UserPreferences
from app.models.profile import Profile, Role
from app.models.report import Report
from app.models.synced_trip import SyncedPlannedHike, SyncedTrip
from app.models.volunteer_hours import HoursState, VolunteerHoursRecord

# Hours a club has already acted on. A `claimed` hour is a logbook entry and
# nobody else's business (VOLUNTEERING.md §5: "the record is theirs first").
# The moment a club admin confirms or disputes it, it is a number somebody
# stood behind and reported upward, and erasing it silently changes a total
# that has already left this building.
#
# @unvalidated - that a club's reported totals would actually move is
# reasoned from the confirm/dispute workflow, not measured; nobody has looked
# at how a club uses `confirmed` hours downstream. What would settle it is
# asking one club admin whether a withdrawn confirmed hour is a correction
# they would want or a number they have already filed.
ACTED_ON_HOURS: tuple[str, ...] = (HoursState.confirmed.value, HoursState.disputed.value)


@dataclass(frozen=True)
class DeletionSummary:
    """What a deletion actually did, per table, for the caller to report back.

    Counted rather than described, because the screen that pressed the button
    is entitled to say "4 trips, 11 preferences" and a hiker deserves to see
    the number rather than the word "done". Every field is a count of rows
    this call changed; a zero is an ordinary answer.
    """

    trips_deleted: int = 0
    planned_hikes_deleted: int = 0
    hikes_deleted: int = 0
    preferences_deleted: int = 0
    assignments_deleted: int = 0
    hours_deleted: int = 0
    hours_kept: int = 0
    app_failures_unlinked: int = 0
    contributions_kept: dict[str, int] = field(default_factory=dict)


def scrub_profile(profile: Profile, now=None) -> None:
    """Empty the row of everything that says who this was, and stamp it.

    Kept separate from `delete_account` so the two halves can be read apart:
    this is the half a reviewer should check against "the person goes", and
    it is deliberately exhaustive rather than clever - a column added to
    `Profile` later is a column this function will not know to clear, which
    is what tests/test_routers_profiles.py's scrub test exists to catch.

    `role` goes back to `hiker` because a deleted maintainer is not a
    maintainer: `require_role` reads this column, and leaving it would make
    the moderation queue reachable by whatever is left of the account.
    """
    profile.display_name = None
    profile.role = Role.hiker
    profile.deleted_at = now or utc_now()


def delete_account(db: Session, profile: Profile, now=None) -> DeletionSummary:
    """Delete everything private, keep everything published, scrub the person.

    Does not commit - the caller owns the transaction, because a deletion
    that half-committed is the one outcome nothing here could put right.

    Returns the counts rather than a bare success, so the endpoint can hand a
    hiker a receipt naming what went.
    """
    now = now or utc_now()
    profile_id = profile.id

    # --- The rows that were only ever theirs. These go outright. ---

    trips = db.query(SyncedTrip).filter(SyncedTrip.profile_id == profile_id).delete(synchronize_session=False)
    planned = db.query(SyncedPlannedHike).filter(SyncedPlannedHike.profile_id == profile_id).delete(synchronize_session=False)
    # The wrong-way alert's server-side reference to which direction they are
    # walking. Nobody else reads it and nothing downstream aggregates it.
    hikes = db.query(Hike).filter(Hike.user_id == profile_id).delete(synchronize_session=False)
    preferences = db.query(UserPreferences).filter(UserPreferences.profile_id == profile_id).delete(synchronize_session=False)
    # A stretch of trail this person had taken on. Deleting the account
    # releases it; leaving it would show a section as covered by somebody who
    # is gone, which is worse than showing it as uncovered.
    assignments = (
        db.query(MaintainerAssignment).filter(MaintainerAssignment.maintainer_id == profile_id).delete(synchronize_session=False)
    )
    hours_gone = (
        db.query(VolunteerHoursRecord)
        .filter(
            VolunteerHoursRecord.user_id == profile_id,
            VolunteerHoursRecord.state.notin_(ACTED_ON_HOURS),
        )
        .delete(synchronize_session=False)
    )

    # --- The rows that name them but are not about them. Link and contact go. ---

    # `reporter_id` is nullable here and null is the ORDINARY state (most app
    # failure reports arrive with no token at all), so this column can do what
    # none of the published ones can: forget. `contact` goes with it - it is a
    # way to reach this person, offered in their own words, and it is the
    # exact retention gap features/IDENTITY_AND_PRIVACY.md names. What stays
    # is `what_happened`: a bug report about the app, which is ours to fix.
    failures = db.query(AppFailure).filter(AppFailure.reporter_id == profile_id).all()
    for failure in failures:
        failure.reporter_id = None
        failure.contact = None

    # --- The rows other people are relying on. Untouched, and counted so the
    # hiker is told rather than left to assume. ---

    kept = _contributions_kept(db, profile_id)
    kept["volunteer hours a club confirmed"] = (
        db.query(VolunteerHoursRecord)
        .filter(
            VolunteerHoursRecord.user_id == profile_id,
            VolunteerHoursRecord.state.in_(ACTED_ON_HOURS),
        )
        .count()
    )

    scrub_profile(profile, now=now)

    return DeletionSummary(
        trips_deleted=trips,
        planned_hikes_deleted=planned,
        hikes_deleted=hikes,
        preferences_deleted=preferences,
        assignments_deleted=assignments,
        hours_deleted=hours_gone,
        hours_kept=kept["volunteer hours a club confirmed"],
        app_failures_unlinked=len(failures),
        contributions_kept={name: count for name, count in kept.items() if count},
    )


def _contributions_kept(db: Session, profile_id: str) -> dict[str, int]:
    """Count what deletion is leaving behind, in words a hiker reads.

    The keys are the phrases the deletion screen and the receipt both use
    (`app/schemas/profile.py`), so the warning before the button and the
    count afterwards cannot drift into describing different things.
    """
    return {
        "closures you reported": db.query(Closure).filter(Closure.reported_by == profile_id).count(),
        "condition reports": db.query(Report).filter(Report.reporter_id == profile_id).count(),
        "trail notes": db.query(FieldNote).filter(FieldNote.reporter_id == profile_id).count(),
        # A flag is a moderation request about somebody ELSE's note, and
        # moderators see only what is flagged (FIELD_NOTES.md §5). Withdrawing
        # it on the way out would silently drop an unreviewed note off the
        # queue, which is a decision about that note rather than about this
        # account.
        "notes you flagged for a moderator": db.query(NoteFlag).filter(NoteFlag.flagged_by == profile_id).count(),
        # The irrevocable one, and the sentence the deletion screen has to
        # say out loud before the button is pressed: a shared photo KEEPS THE
        # TRAIL NAME ON IT. `attribution_name` is non-null by construction
        # because credit is the condition CC BY-SA 4.0 was granted under
        # (#577), and stripping it would break that condition for everyone
        # downstream who took the photo on those terms. Deletion cannot walk
        # a licence back, so this is the one place where "unattributed" is
        # not on offer and a hiker is entitled to know that in advance.
        "photos you shared": db.query(PoiPhoto).filter(PoiPhoto.contributor_id == profile_id).count(),
    }
