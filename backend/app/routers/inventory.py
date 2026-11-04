"""`/clubs/{slug}/inventory` - a club's structure survey (features/STRUCTURE_INVENTORY.md).

#1984 — A club's enrolment, settings and waiver have endpoints, and an
enrolled volunteer is a person `org_access` did not know about - lands the
front of it: a club's survey settings, and a volunteer
enrolling by signing the club's waiver and finishing the field guide. The
records themselves, the review queue, areas, claims, walks and exports
arrive with their own issues and the access rules in
`app/core/inventory_access.py`.

**Nothing here notifies anybody.** OurHike sends no notifications at all
(client/src/test/noNotifications.test.ts); enrolling is a row, not an
announcement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.inventory_access import enrollment_of
from app.core.org_access import OrgAccess, org_access, require_org_admin
from app.core.orm import commit_and_refresh
from app.core.time import utc_now
from app.db.session import get_db
from app.models.club import OrgState
from app.models.inventory import (
    COVERAGE_MIN_RECORDS,
    COVERAGE_WINDOW_DAYS,
    MAX_CLAIM_DAYS_AHEAD,
    STALE_DAYS,
    InventoryClubSettings,
    InventoryEnrollment,
)
from app.schemas.inventory import (
    EnrollmentCreate,
    EnrollmentOut,
    EnrollmentPatch,
    InventorySettingsIn,
    InventorySettingsOut,
)

router = APIRouter(tags=["inventory"])


def _settings_out(row: InventoryClubSettings | None) -> InventorySettingsOut:
    """A club with no settings row reads as the defaults, with enrolment closed."""
    if row is None:
        return InventorySettingsOut(
            waiver_text=None,
            waiver_version=None,
            claim_days_ahead=MAX_CLAIM_DAYS_AHEAD,
            coverage_window_days=COVERAGE_WINDOW_DAYS,
            coverage_min_records=COVERAGE_MIN_RECORDS,
            stale_days=STALE_DAYS,
            publish_locations=False,
            enrolment_open=False,
        )
    return InventorySettingsOut(
        waiver_text=row.waiver_text,
        waiver_version=row.waiver_version,
        claim_days_ahead=row.claim_days_ahead,
        coverage_window_days=row.coverage_window_days,
        coverage_min_records=row.coverage_min_records,
        stale_days=row.stale_days,
        publish_locations=row.publish_locations,
        enrolment_open=bool(row.waiver_text and row.waiver_version),
    )


def _enrollment_out(row: InventoryEnrollment) -> EnrollmentOut:
    return EnrollmentOut(
        id=row.id,
        club_id=row.club_id,
        waiver_version=row.waiver_version,
        waiver_signed_at=row.waiver_signed_at,
        typed_name=row.typed_name,
        training_completed_at=row.training_completed_at,
        field_day_at=row.field_day_at,
        can_survey=row.training_completed_at is not None,
    )


@router.get("/clubs/{slug}/inventory/settings", response_model=InventorySettingsOut)
def read_inventory_settings(access: OrgAccess = Depends(org_access), db: Session = Depends(get_db)) -> InventorySettingsOut:
    """Anybody signed in: the waiver must be readable before it is signed."""
    return _settings_out(db.get(InventoryClubSettings, access.club.id))


def _refuse_a_reused_version(db: Session, club_id: str, row: InventoryClubSettings | None, payload: InventorySettingsIn) -> None:
    """A version names one text, for good, once anybody has signed it.

    A signature records the version it was given against, not the words, so
    the version is the only thing tying a signature to what was agreed. Two
    cases would break that tie:

    - **The same version with different words.** Refused outright, signed
      or not: the version has to pin the words from the first save.
    - **A version somebody signed, coming back after it was replaced or
      cleared.** The settings row keeps only the current text, so once a
      signed version stops being current there is nothing left to compare
      its returning words against. Refused unless it is the current version
      saved with its current words; a returning waiver takes a new version.
      Clearing the waiver and re-saving different words under the old version
      was the way round the first rule that this second one closes.
    """
    if payload.waiver_version is None:
        return
    if row is not None and row.waiver_version == payload.waiver_version:
        if row.waiver_text != payload.waiver_text:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The waiver's words changed but its version did not. Give the new text a new version.",
            )
        return
    signed = (
        db.query(InventoryEnrollment.id)
        .filter(
            InventoryEnrollment.club_id == club_id,
            InventoryEnrollment.waiver_version == payload.waiver_version,
        )
        .first()
    )
    if signed is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Volunteers have already signed version {payload.waiver_version!r}, and its words are no longer "
                "on file to compare against. Give this text a new version."
            ),
        )


def _settings_row(db: Session, club_id: str) -> InventoryClubSettings | None:
    return db.get(InventoryClubSettings, club_id)


def _write_settings(db: Session, club_id: str, payload: InventorySettingsIn) -> InventoryClubSettings:
    """The checks and the write, against the row as it is now."""
    row = _settings_row(db, club_id)
    _refuse_a_reused_version(db, club_id, row, payload)
    if row is None:
        row = InventoryClubSettings(club_id=club_id)
        db.add(row)
    row.waiver_text = payload.waiver_text
    row.waiver_version = payload.waiver_version
    row.claim_days_ahead = payload.claim_days_ahead
    row.coverage_window_days = payload.coverage_window_days
    row.coverage_min_records = payload.coverage_min_records
    row.stale_days = payload.stale_days
    row.updated_at = utc_now()
    db.commit()
    return row


@router.put("/clubs/{slug}/inventory/settings", response_model=InventorySettingsOut)
def write_inventory_settings(
    payload: InventorySettingsIn,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> InventorySettingsOut:
    """A club admin sets the waiver and the thresholds.

    **A version names one text** (`_refuse_a_reused_version`): the same
    version with different words is refused, and so is a version somebody
    has signed once it has stopped being current. A new version is how a
    club changes its waiver. Volunteers who signed an earlier version stay
    enrolled - what a club should ask of them when its waiver changes is not
    decided anywhere yet.

    **Two admins saving a club's first settings at once** both find no row
    and both insert one; the primary key lets one through. The other is
    rolled back and run again against the row that now exists, with every
    check, so it answers as if it had arrived second rather than with a 500.
    """
    if (payload.waiver_text is None) != (payload.waiver_version is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A waiver needs both its text and its version, or neither",
        )
    try:
        row = _write_settings(db, access.club.id, payload)
    except IntegrityError:
        db.rollback()
        row = _write_settings(db, access.club.id, payload)
    db.refresh(row)
    return _settings_out(row)


@router.post(
    "/clubs/{slug}/inventory/enrollments",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
def enrol_in_inventory(
    payload: EnrollmentCreate,
    response: Response,
    access: OrgAccess = Depends(org_access),
    db: Session = Depends(get_db),
) -> EnrollmentOut:
    """Sign the club's waiver by typed name, which enrols the volunteer.

    Any signed-in person: a roving volunteer need not hold anything at the
    club. Asking again answers the enrolment that already exists, with 200
    rather than 201, so a double tap or a retry is not an error.
    """
    # A held (`pending`) registration. Anybody without a seat there never
    # reaches this line: `org_access` answers them the 404 an unknown slug
    # gets, #2018 — Harden the release review's security findings: one
    # domain normaliser, held registrations off public reads, strict Stripe
    # ids and choices, hash-pinned rollup installs. This 409 is what the
    # registration's own seat holders get, who can see it exists.
    if access.club.state == OrgState.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This organization's registration is waiting for somebody at its domain to confirm it, "
                "and nothing about it is published until then, so its survey is not open yet."
            ),
        )
    existing = enrollment_of(db, access.club.id, access.person_id)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _enrollment_out(existing)

    settings_row = db.get(InventoryClubSettings, access.club.id)
    if settings_row is None or not (settings_row.waiver_text and settings_row.waiver_version):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This organization has not written its survey waiver yet, so nobody can join its survey",
        )
    if payload.waiver_version != settings_row.waiver_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The waiver changed since it was shown. Read the current one and sign that.",
        )

    row = InventoryEnrollment(
        club_id=access.club.id,
        person_id=access.person_id,
        waiver_version=settings_row.waiver_version,
        waiver_signed_at=utc_now(),
        typed_name=payload.typed_name,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Two taps that both got past the read above: the unique constraint
        # on (club, person) lets one through, and the other answers it.
        db.rollback()
        response.status_code = status.HTTP_200_OK
        return _enrollment_out(enrollment_of(db, access.club.id, access.person_id))
    db.refresh(row)
    return _enrollment_out(row)


@router.get("/clubs/{slug}/inventory/enrollments/me", response_model=EnrollmentOut | None)
def read_my_inventory_enrollment(access: OrgAccess = Depends(org_access), db: Session = Depends(get_db)) -> EnrollmentOut | None:
    """The caller's enrolment here, or null - not being enrolled is an answer."""
    row = enrollment_of(db, access.club.id, access.person_id)
    return _enrollment_out(row) if row is not None else None


@router.patch("/clubs/{slug}/inventory/enrollments/me", response_model=EnrollmentOut)
def finish_inventory_training(
    payload: EnrollmentPatch,
    access: OrgAccess = Depends(org_access),
    db: Session = Depends(get_db),
) -> EnrollmentOut:
    """The field guide is finished. Saying it twice keeps the first time."""
    row = enrollment_of(db, access.club.id, access.person_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Join this organization's survey before finishing its field guide",
        )
    if row.training_completed_at is None:
        row.training_completed_at = utc_now()
        commit_and_refresh(db, row)
    return _enrollment_out(row)
