"""`/clubs/{slug}/inventory` - a club's structure survey (features/STRUCTURE_INVENTORY.md).

#1984 lands the front of it: a club's survey settings, and a volunteer
enrolling by signing the club's waiver and finishing the field guide. #1985
lands the record itself: an observation's upload. Photos, the review queue,
areas, claims, walks and exports arrive with their own issues, on the
access rules in `app/core/inventory_access.py`.

**Nothing here notifies anybody.** OurHike sends no notifications at all
(client/src/test/noNotifications.test.ts); enrolling is a row, not an
announcement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.inventory_access import enrollment_of, require_inventory_volunteer
from app.core.org_access import OrgAccess, org_access, require_org_admin
from app.core.orm import commit_and_refresh
from app.core.time import to_naive_utc, utc_now
from app.db.session import get_db
from app.models.club import OrgState
from app.models.inventory import (
    COVERAGE_MIN_RECORDS,
    COVERAGE_WINDOW_DAYS,
    MAX_CLAIM_DAYS_AHEAD,
    STALE_DAYS,
    InventoryClubSettings,
    InventoryEnrollment,
    InventoryObservation,
    InventoryPass,
    InventoryStructure,
    StructureStatus,
)
from app.schemas.inventory import (
    EnrollmentCreate,
    EnrollmentOut,
    EnrollmentPatch,
    InventorySettingsIn,
    InventorySettingsOut,
    ObservationCreate,
    ObservationReceipt,
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


@router.put("/clubs/{slug}/inventory/settings", response_model=InventorySettingsOut)
def write_inventory_settings(
    payload: InventorySettingsIn,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> InventorySettingsOut:
    """A club admin sets the waiver and the thresholds.

    **A changed waiver needs a new version.** A signature records the version
    it was given against, not the text; if the text could change under the
    same version, a signature would no longer say which words were agreed
    to. So the same version with different words is refused, and a new
    version is how a club changes its waiver. Volunteers who signed an
    earlier version stay enrolled - what a club should ask of them when its
    waiver changes is not decided anywhere yet.
    """
    if (payload.waiver_text is None) != (payload.waiver_version is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A waiver needs both its text and its version, or neither",
        )
    row = db.get(InventoryClubSettings, access.club.id)
    if (
        row is not None
        and row.waiver_version is not None
        and payload.waiver_version == row.waiver_version
        and payload.waiver_text != row.waiver_text
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The waiver's words changed but its version did not. Give the new text a new version.",
        )
    if row is None:
        row = InventoryClubSettings(club_id=access.club.id)
        db.add(row)
    row.waiver_text = payload.waiver_text
    row.waiver_version = payload.waiver_version
    row.claim_days_ahead = payload.claim_days_ahead
    row.coverage_window_days = payload.coverage_window_days
    row.coverage_min_records = payload.coverage_min_records
    row.stale_days = payload.stale_days
    row.updated_at = utc_now()
    return _settings_out(commit_and_refresh(db, row))


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


# A merge chain longer than this is a loop somebody made by hand, not a club
# merging duplicates; refusing it beats following it forever.
MAX_MERGE_HOPS = 8


def _receipt(row: InventoryObservation) -> ObservationReceipt:
    return ObservationReceipt(
        observation_id=row.id,
        structure_id=row.structure_id,
        review_state=row.review_state,
        mile=row.mile,
        off_line_ft=row.off_line_ft,
    )


def _already_uploaded(db: Session, observation_id: str, enrollment: InventoryEnrollment) -> InventoryObservation | None:
    """The same record sent again answers itself; somebody else's id is refused.

    The refusal does not say whose it is, or at which club: a record id is a
    client's UUID and nobody should learn anything by guessing one.
    """
    row = db.get(InventoryObservation, observation_id)
    if row is None:
        return None
    if row.club_id == enrollment.club_id and row.volunteer_id == enrollment.person_id:
        return row
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That record id is already taken")


def _structure_for(db: Session, payload: ObservationCreate, enrollment: InventoryEnrollment) -> InventoryStructure:
    """The structure this visit is to, created when its id is new.

    A structure since merged into another is followed to the one it turned
    out to be: the volunteer saw it before the merge, and their visit is to
    the same physical thing. A structure id from another club is refused
    the way a taken record id is.
    """
    structure_id = str(payload.structure_id)
    structure = db.get(InventoryStructure, structure_id)
    if structure is None:
        if payload.kind is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A structure nobody has logged before needs its kind",
            )
        structure = InventoryStructure(
            id=structure_id,
            club_id=enrollment.club_id,
            kind=payload.kind,
            subkind=payload.subkind,
            lat=payload.lat,
            lon=payload.lon,
            created_by=enrollment.person_id,
        )
        db.add(structure)
        # Flushed now: these models declare no relationships, so nothing else
        # tells the session to insert the structure before the record on it.
        db.flush()
        return structure
    if structure.club_id != enrollment.club_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That structure id is already taken")
    for _ in range(MAX_MERGE_HOPS):
        if structure.status != StructureStatus.merged or structure.merged_into_id is None:
            break
        structure = db.get(InventoryStructure, structure.merged_into_id)
    else:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That structure's merges loop back on themselves")
    if payload.kind is not None and payload.kind != structure.kind:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"That structure is logged as a {structure.kind.value}, not a {payload.kind.value}",
        )
    return structure


@router.post(
    "/clubs/{slug}/inventory/observations",
    response_model=ObservationReceipt,
    status_code=status.HTTP_201_CREATED,
)
def upload_inventory_observation(
    payload: ObservationCreate,
    response: Response,
    enrollment: InventoryEnrollment = Depends(require_inventory_volunteer),
    db: Session = Depends(get_db),
) -> ObservationReceipt:
    """One visit to one structure, from the outbox. Idempotent on its id.

    **A second POST with the same id answers the same row and changes
    nothing**, with 200 rather than 201: the outbox retries until it hears
    back, and a retry that rewrote the record would let a stale copy on the
    phone overwrite one a reviewer has already acted on.

    **Every reading is kept whole** (rule 2), and the server counts them.
    **Unsafe sets nothing special on the row**: the review queue orders by
    `condition`, and the email to the club's admins is #1992's.
    """
    observation_id = str(payload.id)
    existing = _already_uploaded(db, observation_id, enrollment)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _receipt(existing)

    structure = _structure_for(db, payload, enrollment)

    pass_id = str(payload.pass_id) if payload.pass_id is not None else None
    if pass_id is not None:
        walk = db.get(InventoryPass, pass_id)
        if walk is None or walk.club_id != enrollment.club_id or walk.volunteer_id != enrollment.person_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="That walk is not one of yours at this organization",
            )

    same_as = str(payload.same_as_structure_id) if payload.same_as_structure_id is not None else None
    if same_as is not None:
        other = db.get(InventoryStructure, same_as)
        if other is None or other.club_id != enrollment.club_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="That structure is not in this organization's inventory",
            )

    row = InventoryObservation(
        id=observation_id,
        structure_id=structure.id,
        club_id=enrollment.club_id,
        pass_id=pass_id,
        volunteer_id=enrollment.person_id,
        captured_at=to_naive_utc(payload.captured_at),
        offline=payload.offline,
        lat=payload.lat,
        lon=payload.lon,
        accuracy_m=payload.accuracy_m,
        readings_count=len(payload.readings),
        readings_seconds=payload.readings_seconds,
        readings=[reading.model_dump() for reading in payload.readings],
        fix_source=payload.fix_source,
        gps_lock=payload.gps_lock,
        satellites=payload.satellites,
        connection=payload.connection,
        same_as_structure_id=same_as,
        condition=payload.condition,
        problems=list(payload.problems),
        repair=payload.repair,
        timing=payload.timing,
        size_bucket=payload.size_bucket,
        size_measured=payload.size_measured,
        size_unit=payload.size_unit,
        size_method=payload.size_method,
        counts=payload.counts,
        railings=payload.railings,
        notes=payload.notes,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Two sends of one record racing past the read above: the primary
        # key lets one through, and the other answers it - or is refused, if
        # the id turned out to be somebody else's.
        db.rollback()
        existing = _already_uploaded(db, observation_id, enrollment)
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return _receipt(existing)
    db.refresh(row)
    return _receipt(row)
