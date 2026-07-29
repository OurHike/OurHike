"""`/reports` endpoints - community condition reports.

See ../../../features/REPORT_A_PROBLEM.md. Browsing (`GET`) needs no
account, matching every other browsing endpoint in this app; submitting
(`POST`) requires a real identity so a report has a reporter to attribute
it to and, later, moderate against.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth import bearer_scheme, get_current_user
from app.db.session import get_db
from app.models.profile import Profile
from app.models.report import Report, ReportStatus, ReportType, Visibility
from app.schemas.report import ReportCreate, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])

# `bad_hikers` is the one type that reports on people rather than trail
# conditions - REPORT_A_PROBLEM.md's "Bad hikers needs different handling"
# section routes it privately to maintainers/moderators instead of a
# public map pin; every other type defaults to public.
_INTERNAL_ONLY_TYPES = {ReportType.bad_hikers}


def _visibility_for(report_type: ReportType) -> Visibility:
    return Visibility.internal_only if report_type in _INTERNAL_ONLY_TYPES else Visibility.public


def _get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Profile | None:
    """Like `get_current_user`, but returns None instead of raising.

    Used by endpoints that work with or without auth (browsing needs no
    account) but still want to know who's asking, if anyone, e.g. so a
    reporter can see their own otherwise-hidden report.
    """
    if credentials is None:
        return None
    try:
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


def _visible_to(report: Report, viewer: Profile | None) -> bool:
    """Whether `viewer` (possibly anonymous) may see `report`.

    The reporter can always see their own report, regardless of visibility
    or status. Everyone else only sees reports that are public and not
    dismissed - matching the list endpoint's filter exactly.
    """
    if viewer is not None and report.reporter_id == viewer.id:
        return True
    return report.visibility == Visibility.public and report.status != ReportStatus.dismissed


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    """Submit a new report. `visibility` and `severity` are never taken
    from the request - `visibility` is derived from `type` here, and
    `severity` stays at the model's `normal` default until a later verify
    action (built elsewhere) can raise it."""
    report = Report(
        reporter_id=current_user.id,
        type=payload.type,
        poi_id=payload.poi_id,
        lat=payload.lat,
        lon=payload.lon,
        reporter_type=payload.reporter_type,
        note=payload.note,
        photo_url=payload.photo_url,
        visibility=_visibility_for(payload.type),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=list[ReportOut])
def list_reports(db: Session = Depends(get_db)) -> list[Report]:
    """List reports visible to an anonymous/non-owning caller: public and
    not dismissed. No auth required - browsing needs no account."""
    return db.query(Report).filter(Report.visibility == Visibility.public, Report.status != ReportStatus.dismissed).all()


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: Profile | None = Depends(_get_current_user_optional),
) -> Report:
    """Return a single report, with the same visibility filtering as the
    list endpoint - except the reporter can always see their own report."""
    report = db.get(Report, report_id)
    if report is None or not _visible_to(report, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report
