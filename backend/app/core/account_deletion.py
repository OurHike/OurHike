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

The takedown ledger, `poi_photo_dismissals` (#1551). It names the hiker as
the contributor whose photo came down, and it is a moderator's record in
the same sense `reports.dismissed_by` is: somebody else's decision, kept so
the next moderator can see a pattern. Not counted on the receipt, because
it is not a contribution that stayed - it is a record about the account,
and the export hands the hiker their own rows from it.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.app_failure import AppFailure
from app.models.closure import Closure, ClosureApproval
from app.models.club import Club, OrgAdmin
from app.models.console_key import ConsoleKey
from app.models.field_note import FieldNote, NoteFlag
from app.models.hike import Hike
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_registry import RegistrySignoff
from app.models.org_role import RoleInvite, RosterSyncRun
from app.models.poi_photo import PoiPhoto
from app.models.preferences import UserPreferences
from app.models.profile import Profile, Role
from app.models.report import Report
from app.models.ridge_runner import RidgeRunnerCommitment
from app.models.synced_day_hike import SyncedDayHike
from app.models.synced_hike import SyncedActiveHike, SyncedHike
from app.models.synced_trip import SyncedPlannedHike, SyncedTrip
from app.models.volunteer_hours import HoursState, VolunteerHoursRecord
from app.models.work_project import WorkProject, WorkProjectSignup

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
    day_hikes_deleted: int = 0
    #: The long hikes that grouped them (#1317). The pointer at whichever one
    #: was leading has no count of its own - see `delete_account`.
    long_hikes_deleted: int = 0
    planned_hikes_deleted: int = 0
    hikes_deleted: int = 0
    preferences_deleted: int = 0
    assignments_deleted: int = 0
    hours_deleted: int = 0
    hours_kept: int = 0
    #: The organization surface (features/ORG_ONBOARDING.md). A seat and a
    #: signup are both permissions rather than contributions, so both go -
    #: see the reasoning at each query in `delete_account`.
    org_seats_released: int = 0
    registry_signatures_withdrawn: int = 0
    workday_signups_released: int = 0
    commitments_deleted: int = 0
    org_rows_unlinked: int = 0
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
    # A GitHub login names the person as surely as a display name does, and
    # it is a CODEOWNERS entry while it stays (#1635). `github_login` is
    # also unique, so leaving it here kept that account from being linked to
    # anybody - including the same person signing up again.
    profile.github_login = None
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
    # Same claim as trips, same answer: a synced day hike is the hiker's own
    # private planning (#976), published to nobody and relied on by nobody.
    day_hikes = db.query(SyncedDayHike).filter(SyncedDayHike.profile_id == profile_id).delete(synchronize_session=False)
    # The long hikes themselves (#1317), and the pointer at whichever one
    # the app was in. Same claim again: a hiker's own record of where they
    # have walked, published to nobody. The POINTER is deleted without a
    # count of its own - it is one id saying which hike was leading, not a
    # thing anybody would miss - where the hikes are counted, because a
    # receipt that lists trips and day hikes and silently omits the object
    # holding years of them is a receipt that understates itself.
    long_hikes = db.query(SyncedHike).filter(SyncedHike.profile_id == profile_id).delete(synchronize_session=False)
    db.query(SyncedActiveHike).filter(SyncedActiveHike.profile_id == profile_id).delete(synchronize_session=False)
    planned = db.query(SyncedPlannedHike).filter(SyncedPlannedHike.profile_id == profile_id).delete(synchronize_session=False)
    # Originally the wrong-way alert's server-side reference to which
    # direction they were walking (feature removed, #93/#308). Nobody reads
    # it and nothing downstream aggregates it; the table stays for API
    # compatibility (app/models/hike.py) but a deleted account's rows go too.
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

    # A seat at an organization is a PERMISSION, not a contribution. A
    # deleted account cannot administer anything, and a row saying it can is
    # a codeowner the organization would be waiting on forever - the same
    # argument as the assignment above, where showing a section as covered by
    # somebody who is gone is worse than showing it as uncovered.
    org_seats = db.query(OrgAdmin).filter(OrgAdmin.person_id == profile_id).delete(synchronize_session=False)

    # A SIGNATURE CANNOT OUTLIVE ITS SIGNER, and this is the one row here
    # where that is a safety property rather than tidiness. A registry
    # sign-off says a named person read this exact registry and confirmed it
    # is accurate; with the account gone there is nobody standing behind that
    # sentence, and a count of three that includes a deleted signer is three
    # people the organization thinks read something.
    #
    # Deleting it is safe and self-correcting: nothing is unpublished, the
    # count simply drops below `REGISTRY_APPROVALS_REQUIRED` and the
    # remaining codeowners are asked again - exactly what the fingerprint
    # already does when a section changes. See app/routers/org_registry.py.
    registry_signatures = (
        db.query(RegistrySignoff).filter(RegistrySignoff.person_id == profile_id).delete(synchronize_session=False)
    )

    # A hand put up for a workday, and a crew slot the organization may have
    # allocated. Released for the same reason: an organization planning
    # Saturday is better served by a free slot than by a name nobody can
    # reach. VOLUNTEERING.md's "an introduction, not an enrolment" cuts this
    # way too - nothing was ever a roster entry to preserve.
    signups = db.query(WorkProjectSignup).filter(WorkProjectSignup.person_id == profile_id).delete(synchronize_session=False)

    # The commitment window is a mode the app was in for this person, visible
    # to nobody else and issuing nothing that functions as a badge
    # (VOLUNTEERING.md §3). There is no third party relying on it.
    commitments = (
        db.query(RidgeRunnerCommitment).filter(RidgeRunnerCommitment.person_id == profile_id).delete(synchronize_session=False)
    )

    # --- Organization rows that NAME them and belong to the organization.
    # Every one of these columns is nullable, so the link can be forgotten
    # while the row goes on being the organization's - the same thing
    # `app_failures.reporter_id` does below, applied to four more tables. An
    # organization does not lose its registry, its workdays, its audit trail
    # or its embed keys because one of its admins closed their OurHike
    # account. ---

    unlinked = 0
    for model, column in (
        (Club, Club.created_by),
        # The organization's agreement that a model may read its data
        # survives the admin who recorded it - it was the organization's
        # decision, and it does not lapse because one person closed their
        # account. Their id does not survive it: `assist_opted_in_at` stays
        # where it is and the name beside it goes, which is the same trade
        # every row in this loop makes.
        (Club, Club.assist_opted_in_by),
        (WorkProject, WorkProject.created_by),
        (ConsoleKey, ConsoleKey.created_by),
        (RosterSyncRun, RosterSyncRun.run_by),
        (RoleInvite, RoleInvite.invited_by),
    ):
        for row in db.query(model).filter(column == profile_id).all():
            setattr(row, column.key, None)
            unlinked += 1

    # An invite this person CLAIMED is the audit row for a grant that has just
    # gone with them, so it goes too rather than pointing at an account
    # nobody can sign into. An invite they SENT is the organization's, and is
    # unlinked above.
    unlinked += db.query(RoleInvite).filter(RoleInvite.claimed_by == profile_id).delete(synchronize_session=False)

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

    # A condition report stays - other people rely on it - but the name the
    # hiker signed it with and their consent to be contacted go (#1563), for
    # exactly the reason `contact` goes above: both were offered by a person
    # who is now gone, and a real name on a row that outlives the account is
    # the retention gap features/IDENTITY_AND_PRIVACY.md names. `reporter_id`
    # stays, as it always has: the profile it points at is scrubbed below.
    for report in db.query(Report).filter(Report.reporter_id == profile_id).all():
        report.signed_name = None
        report.signed_name_kind = None
        report.contact_ok = False

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
        day_hikes_deleted=day_hikes,
        long_hikes_deleted=long_hikes,
        planned_hikes_deleted=planned,
        hikes_deleted=hikes,
        preferences_deleted=preferences,
        assignments_deleted=assignments,
        hours_deleted=hours_gone,
        hours_kept=kept["volunteer hours a club confirmed"],
        app_failures_unlinked=len(failures),
        org_seats_released=org_seats,
        registry_signatures_withdrawn=registry_signatures,
        workday_signups_released=signups,
        commitments_deleted=commitments,
        org_rows_unlinked=unlinked,
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
        # An approval is a statement about a closure other hikers are already
        # routing around - the same class of row as the closure itself, which
        # this function has always kept. Withdrawing one could drop a closure
        # back below the three it needed, which is a decision about that
        # closure rather than about this account.
        "closures you helped confirm": db.query(ClosureApproval).filter(ClosureApproval.person_id == profile_id).count(),
    }
