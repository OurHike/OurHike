"""The moderation queue: reading what is waiting, and verifying/dismissing
it - for both Report and Closure.

See ../../../features/REPORT_A_PROBLEM.md's "Architecture fit" section and
../../../features/HIKER_SAFETY.md §1. Both resources reuse this one
workflow rather than each growing its own review mechanism - REPORT_A_PROBLEM.md
explicitly names Closures and Hiker Safety's warning escalation as reusing
its moderation queue directly, "not building a second review workflow".

Escalating a report to `severity=serious` happens *during this same verify
action* - not a separate step, and not gated on any corroboration count.
HIKER_SAFETY.md itself calls the exact corroboration threshold "real
moderation policy, not a data-model question" and leaves it genuinely
undecided; this router only enforces *who* can make that judgment call
(maintainer/club_admin), never *how much evidence* they should personally
require first - that's left to the human doing the verifying.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.orm import commit_and_refresh, get_or_404
from app.core.photos import (
    PhotoStorageUnavailable,
    delete_photo_object,
    photo_storage_configured,
    poi_photo_key,
    presigned_object_url,
)
from app.core.time import utc_now
from app.db.session import get_db
from app.models.closure import Closure, ModerationStatus
from app.models.poi_photo import PoiPhoto, PoiPhotoStatus
from app.models.profile import MODERATOR_ROLES, Profile
from app.models.report import Report, ReportStatus, ReportType
from app.routers.poi_photos import PINNED_MAX
from app.schemas.closure import ClosureVerify
from app.schemas.moderation import ClosureModerationOut, ModerationQueue, ReportVerifyRequest
from app.schemas.poi_photo import PoiPhotoModerationOut
from app.schemas.report import ReportOut

router = APIRouter(tags=["moderation"])


@router.get("/moderation/queue", response_model=ModerationQueue)
def read_moderation_queue(
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> ModerationQueue:
    """Everything waiting on a moderator: submitted reports and submitted
    closures.

    Until this existed the queue could be acted on but not read. Every
    endpoint below takes an id, and the only two list endpoints are scoped to
    the public - `/reports` to what has already been moderated, `/closures`
    to `moderation_status == verified`, i.e. precisely the ones already done.
    Nothing returned the ids of the items waiting.

    **The sharp end of that was `bad_hikers`.** Those are forced to
    `visibility = internal_only` on create (app/routers/reports.py), and
    `internal_only` appeared in exactly one query in this codebase - the
    public list, which excludes it. So a report about being followed on trail
    could be filed and then read by nobody but its own author.
    REPORT_A_PROBLEM.md chose that visibility to mean "route it privately to
    club maintainers/moderators as an incident note"; half of that was built
    (it is not a public pin) and the half that delivers it was not. Hence no
    visibility filter here: this endpoint is the audience `internal_only`
    always named.

    `thanks` is excluded because `verify_report` below refuses it outright -
    gratitude has nothing to verify (SAYING_THANKS.md), and listing it here
    would put items in the queue whose only available action is a 409, in the
    queue closures and serious warnings share.

    **Not answered here, and both are real:** REPORT_A_PROBLEM.md's own open
    questions ask whether a `bad_hikers` report should route to the nearest
    club, a general inbox, or both, and HIKER_SAFETY.md §1 leaves the
    corroboration bar for escalating a dangerous-person report as "real
    moderation policy, not a data-model question". This lists everything
    pending to any maintainer, which is enough for one club and is not
    enough to ship to thirty.
    """
    reports = db.query(Report).filter(Report.status == ReportStatus.submitted, Report.type != ReportType.thanks).all()
    closures = db.query(Closure).filter(Closure.moderation_status == ModerationStatus.submitted).all()

    return ModerationQueue(
        # A moderator sees the whole record - schemas/moderation.py explains
        # why the queue reuses ReportOut rather than a leaner row, and #252
        # does not change that: what it changes is what the PUBLIC sees.
        reports=[ReportOut.for_viewer(report, current_user) for report in reports],
        closures=[ClosureModerationOut.model_validate(closure) for closure in closures],
    )


@router.post("/reports/{report_id}/verify", response_model=ReportOut)
def verify_report(
    report_id: str,
    payload: ReportVerifyRequest,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> ReportOut:
    report = get_or_404(db, Report, report_id, detail="Report not found")

    # A thanks is not a claim about the world, so there is nothing to verify
    # (../../../features/SAYING_THANKS.md). Refused here rather than merely
    # hidden in the UI, so gratitude cannot end up in the queue that closures
    # and warnings share and bury real safety work. Dismissal stays available
    # below - that is abuse removal, which is a different action.
    if report.type is ReportType.thanks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A thanks has nothing to verify.",
        )

    # Resolved is terminal for verification: it means "was verified, then
    # fixed", and re-verifying would quietly re-open a hazard the record
    # says is cleared. Dismissal below stays available from any state -
    # abuse removal always is (#658).
    if report.status is ReportStatus.resolved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This report is resolved. File a new report for a recurrence.",
        )

    report.status = ReportStatus.verified
    # Only when the moderator actually said something about it. An omitted
    # severity is not a de-escalation - see ReportVerifyRequest (#251).
    if payload.severity is not None:
        report.severity = payload.severity

    # The same two fields verify_closure has set all along. Without them
    # "who marked this dangerous-person report serious, and when" was
    # unanswerable for the one resource where it matters most, while being
    # answerable for a washed-out footbridge - which made
    # features/REPORT_A_PROBLEM.md's "not building a second review workflow"
    # structurally false at exactly this point.
    #
    # Set once, never overwritten (#658): who FIRST escalated a
    # dangerous-person report is the fact an audit needs, and a re-verify
    # used to replace it with whoever touched the row last.
    if report.verified_at is None:
        report.verified_by = current_user.id
        report.verified_at = utc_now()
    return ReportOut.for_viewer(commit_and_refresh(db, report), current_user)


@router.post("/reports/{report_id}/dismiss", response_model=ReportOut)
def dismiss_report(
    report_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> ReportOut:
    report = get_or_404(db, Report, report_id, detail="Report not found")

    report.status = ReportStatus.dismissed
    # Latest-wins, where verified_* preserves the first (#658): "who removed
    # this bad_hikers report" means the operative removal, and until these
    # two were recorded it was unanswerable while "who escalated it" was not.
    report.dismissed_by = current_user.id
    report.dismissed_at = utc_now()
    return ReportOut.for_viewer(commit_and_refresh(db, report), current_user)


@router.post("/reports/{report_id}/resolve", response_model=ReportOut)
def resolve_report(
    report_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> ReportOut:
    """Mark a verified hazard as fixed - the action that makes
    `ReportStatus.resolved` reachable (#658).

    The status has been load-bearing and unreachable since #257: the public
    contract keeps resolved reports visible, the client renders them as
    "Fixed" (lib/reportStatus.ts), and no endpoint could set it - so a
    cleared blowdown could only be vanished by dismissal, which reads as
    "this was never real" rather than "this was real and someone fixed it".

    Only from `verified`. Resolving a `submitted` report would skip the
    moderation gate ("fixed" implies "was real", and only verify says that);
    resolving a `dismissed` one would resurrect a report a moderator
    removed. Resolving an already-resolved report is a no-op 200 - retries
    are normal and there is nothing further to record.
    """
    report = get_or_404(db, Report, report_id, detail="Report not found")

    if report.status is ReportStatus.resolved:
        return ReportOut.for_viewer(report, current_user)
    if report.status is not ReportStatus.verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a verified report can be resolved.",
        )

    report.status = ReportStatus.resolved
    report.resolved_by = current_user.id
    report.resolved_at = utc_now()
    return ReportOut.for_viewer(commit_and_refresh(db, report), current_user)


@router.post("/closures/{closure_id}/verify", response_model=ClosureModerationOut)
def verify_closure(
    closure_id: str,
    payload: ClosureVerify | None = None,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> Closure:
    """Publish a closure to every hiker on the trail.

    The body is optional and usually absent. A closure is born `closed`
    (app/models/closure.py), so verifying one says everything that needs
    saying - the band and the banner appear because the record was already
    true, not because this call fixed it up.

    Passing `status` covers the one judgment that genuinely happens here:
    confirming a reroute. See ClosureVerify.
    """
    closure = get_or_404(db, Closure, closure_id, detail="Closure not found")

    closure.moderation_status = ModerationStatus.verified
    # Set once, never overwritten - same rule and reason as verify_report.
    if closure.verified_at is None:
        closure.verified_by = current_user.id
        closure.verified_at = utc_now()
    if payload is not None and payload.status is not None:
        closure.status = payload.status
    return commit_and_refresh(db, closure)


@router.post("/closures/{closure_id}/dismiss", response_model=ClosureModerationOut)
def dismiss_closure(
    closure_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> Closure:
    closure = get_or_404(db, Closure, closure_id, detail="Closure not found")

    closure.moderation_status = ModerationStatus.dismissed
    # Latest-wins - same rule and reason as dismiss_report (#658).
    closure.dismissed_by = current_user.id
    closure.dismissed_at = utc_now()
    return commit_and_refresh(db, closure)


# --- Community waypoint photos (#579) --------------------------------------
#
# The photo half of this same queue, against the #576 store. The design's
# split is what keeps it affordable (POI_PHOTOS.md): only pins are
# pre-moderated, so this surface exists to promote - the rolling twelve go
# straight up and come down when somebody reports one. What sorts to the
# top is what needs a person soonest: a nudity hold (nothing is public
# while it waits), then a report that somebody in the photo did not agree,
# then other reports; below that, recency orders the list and never
# promotes anything.


@router.get("/moderation/poi-photos", response_model=list[PoiPhotoModerationOut])
def read_photo_queue(
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """Every live, uploaded community photo, most decision-worthy first.

    Moderators see the queue regardless of the public gallery's cooling-off
    window - a pin decision two hours early is fine because the PIN action
    is what publishes, and it never fires inside somebody's undo window
    (the gallery filter holds for pins too). The trail name stays masked
    here exactly as on the card: the queue judges photographs, not
    photographers.

    Empty where storage is unconfigured - a queue of unsignable URLs is a
    wall of broken images, not a queue.
    """
    if not photo_storage_configured():
        return []

    attention = case(
        ((PoiPhoto.flagged == "nudity") & PoiPhoto.reviewed_at.is_(None), 0),
        (PoiPhoto.reported_at.isnot(None) & (PoiPhoto.reported_reason == "person") & PoiPhoto.reviewed_at.is_(None), 1),
        (PoiPhoto.reported_at.isnot(None) & PoiPhoto.reviewed_at.is_(None), 2),
        else_=3,
    )
    photos = (
        db.query(PoiPhoto)
        .filter(PoiPhoto.status == PoiPhotoStatus.live, PoiPhoto.uploaded_at.isnot(None))
        .order_by(attention, PoiPhoto.uploaded_at.desc(), PoiPhoto.id)
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        PoiPhotoModerationOut.from_moderation_row(
            photo,
            url=presigned_object_url(poi_photo_key(photo.poi_id, photo.contributor_id)),
        )
        for photo in photos
    ]


@router.post("/moderation/poi-photos/{photo_id}/pin", response_model=PoiPhotoModerationOut)
def pin_photo(
    photo_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
):
    """Make this one of the place's pinned three - rung 2's editorial pick.

    Refused at the cap with the collision the queue mockup draws: pinning a
    fourth means choosing which of the three comes down first, and that
    choice belongs to the person, not to recency. Pinning is also the human
    glance - it clears any hold or report, because a moderator who chose to
    put a photo on the card has looked at it as hard as this queue ever
    asks anyone to.
    """
    photo = get_or_404(db, PoiPhoto, photo_id, detail="Photo not found")
    if photo.status is not PoiPhotoStatus.live or photo.uploaded_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a live, uploaded photo can be pinned.")

    if photo.pinned_at is None:
        pinned = (
            db.query(PoiPhoto)
            .filter(
                PoiPhoto.poi_id == photo.poi_id,
                PoiPhoto.status == PoiPhotoStatus.live,
                PoiPhoto.pinned_at.isnot(None),
            )
            .count()
        )
        if pinned >= PINNED_MAX:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This place already has {PINNED_MAX} pins. Unpin one first, or leave this in the rolling twelve.",
            )
        photo.pinned_at = utc_now()
        photo.pinned_by = current_user.id

    if photo.reviewed_at is None:
        photo.reviewed_at = utc_now()
        photo.reviewed_by = current_user.id

    commit_and_refresh(db, photo)
    return PoiPhotoModerationOut.from_moderation_row(
        photo, url=presigned_object_url(poi_photo_key(photo.poi_id, photo.contributor_id))
    )


@router.post("/moderation/poi-photos/{photo_id}/unpin", response_model=PoiPhotoModerationOut)
def unpin_photo(
    photo_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
):
    """Take a pin down. The photo itself is untouched - it rejoins the
    rolling twelve and ages out by recency like any other, which is the
    difference between unpinning and refusing."""
    photo = get_or_404(db, PoiPhoto, photo_id, detail="Photo not found")
    photo.pinned_at = None
    photo.pinned_by = None
    commit_and_refresh(db, photo)
    return PoiPhotoModerationOut.from_moderation_row(
        photo, url=presigned_object_url(poi_photo_key(photo.poi_id, photo.contributor_id))
    )


@router.post("/moderation/poi-photos/{photo_id}/review", response_model=PoiPhotoModerationOut)
def review_photo(
    photo_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
):
    """The queue's "leave it in the twelve": one human looked and the photo
    is fine where it is. Clears a nudity hold (the photo then serves once
    its cooling-off window ends) and answers a report without acting on it.
    Latest-look-wins, so re-reviewing after a fresh report is ordinary."""
    photo = get_or_404(db, PoiPhoto, photo_id, detail="Photo not found")
    photo.reviewed_at = utc_now()
    photo.reviewed_by = current_user.id
    commit_and_refresh(db, photo)
    return PoiPhotoModerationOut.from_moderation_row(
        photo, url=presigned_object_url(poi_photo_key(photo.poi_id, photo.contributor_id))
    )


@router.post("/moderation/poi-photos/{photo_id}/dismiss", response_model=PoiPhotoModerationOut)
def dismiss_photo(
    photo_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
):
    """The takedown - what makes #576's withdrawal promise two-sided: the
    photographer can always withdraw, and now a person with standing can
    take a photo down that its photographer would not.

    The row stays as the moderation trail (#658's who-took-this-down, on
    the resource where a photo of a person is the stakes); the OBJECT is
    deleted, because the bytes of a refused photograph are risk, not
    record. Latest-wins on the trail columns, same as every dismissal.
    """
    photo = get_or_404(db, PoiPhoto, photo_id, detail="Photo not found")

    photo.status = PoiPhotoStatus.dismissed
    photo.dismissed_at = utc_now()
    photo.dismissed_by = current_user.id
    photo.pinned_at = None
    photo.pinned_by = None
    commit_and_refresh(db, photo)

    try:
        delete_photo_object(poi_photo_key(photo.poi_id, photo.contributor_id))
    except PhotoStorageUnavailable:
        # The row's status is the authoritative half and it is already
        # dismissed; the object is an orphan for the sweep.
        pass

    return PoiPhotoModerationOut.from_moderation_row(
        photo, url=presigned_object_url(poi_photo_key(photo.poi_id, photo.contributor_id))
    )
