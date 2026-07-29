"""Moderation-queue actions: verify/dismiss for both Report and Closure.

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

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.db.session import get_db
from app.models.closure import Closure, ModerationStatus
from app.models.profile import Profile
from app.models.report import Report, ReportStatus
from app.schemas.closure import ClosureOut
from app.schemas.moderation import ReportVerifyRequest
from app.schemas.report import ReportOut

router = APIRouter(tags=["moderation"])


@router.post("/reports/{report_id}/verify", response_model=ReportOut)
def verify_report(
    report_id: str,
    payload: ReportVerifyRequest,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
    db: Session = Depends(get_db),
) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    report.status = ReportStatus.verified
    report.severity = payload.severity
    db.commit()
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/dismiss", response_model=ReportOut)
def dismiss_report(
    report_id: str,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
    db: Session = Depends(get_db),
) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    report.status = ReportStatus.dismissed
    db.commit()
    db.refresh(report)
    return report


@router.post("/closures/{closure_id}/verify", response_model=ClosureOut)
def verify_closure(
    closure_id: str,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
    db: Session = Depends(get_db),
) -> Closure:
    closure = db.get(Closure, closure_id)
    if closure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Closure not found")

    closure.moderation_status = ModerationStatus.verified
    closure.verified_by = current_user.id
    closure.verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(closure)
    return closure


@router.post("/closures/{closure_id}/dismiss", response_model=ClosureOut)
def dismiss_closure(
    closure_id: str,
    current_user: Profile = Depends(require_role("maintainer", "club_admin")),
    db: Session = Depends(get_db),
) -> Closure:
    closure = db.get(Closure, closure_id)
    if closure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Closure not found")

    closure.moderation_status = ModerationStatus.dismissed
    db.commit()
    db.refresh(closure)
    return closure
