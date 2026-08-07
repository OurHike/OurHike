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
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.orm import commit_and_refresh, get_or_404
from app.core.time import utc_now
from app.db.session import get_db
from app.models.closure import Closure, ModerationStatus
from app.models.profile import Profile
from app.models.report import Report, ReportStatus, ReportType
from app.schemas.closure import ClosureOut, ClosureVerify
from app.schemas.moderation import ModerationQueue, ReportVerifyRequest
from app.schemas.report import ReportOut

router = APIRouter(tags=["moderation"])


@router.get("/moderation/queue", response_model=ModerationQueue)
def read_moderation_queue(
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
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
        reports=[ReportOut.model_validate(report) for report in reports],
        closures=[ClosureOut.model_validate(closure) for closure in closures],
    )


@router.post("/reports/{report_id}/verify", response_model=ReportOut)
def verify_report(
    report_id: str,
    payload: ReportVerifyRequest,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
    db: Session = Depends(get_db),
) -> Report:
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

    report.status = ReportStatus.verified
    report.severity = payload.severity
    return commit_and_refresh(db, report)


@router.post("/reports/{report_id}/dismiss", response_model=ReportOut)
def dismiss_report(
    report_id: str,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
    db: Session = Depends(get_db),
) -> Report:
    report = get_or_404(db, Report, report_id, detail="Report not found")

    report.status = ReportStatus.dismissed
    return commit_and_refresh(db, report)


@router.post("/closures/{closure_id}/verify", response_model=ClosureOut)
def verify_closure(
    closure_id: str,
    payload: ClosureVerify | None = None,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
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
    closure.verified_by = current_user.id
    closure.verified_at = utc_now()
    if payload is not None and payload.status is not None:
        closure.status = payload.status
    return commit_and_refresh(db, closure)


@router.post("/closures/{closure_id}/dismiss", response_model=ClosureOut)
def dismiss_closure(
    closure_id: str,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
    db: Session = Depends(get_db),
) -> Closure:
    closure = get_or_404(db, Closure, closure_id, detail="Closure not found")

    closure.moderation_status = ModerationStatus.dismissed
    return commit_and_refresh(db, closure)
