"""`/clubs/{slug}/inventory` - a club's structure survey (features/STRUCTURE_INVENTORY.md).

Three issues land the front of it, on the access rules in
`app/core/inventory_access.py`:

- #1984 — A club's enrolment, settings and waiver have endpoints, and an
  enrolled volunteer is a person `org_access` did not know about: a club's
  survey settings, and a volunteer enrolling by signing the club's waiver
  and finishing the field guide.
- #1985 — An observation uploads once, idempotent on its id, creates its
  structure when the structure is new, and keeps every GPS reading it was
  given: the record itself.
- #1986 — Observation photos use the report pipeline with a key of their own
  and no table: the record's photos.

The review queue, areas, claims, walks and exports arrive with their own
issues.

**Nothing here notifies anybody.** OurHike sends no notifications at all
(client/src/test/noNotifications.test.ts); enrolling is a row, not an
announcement.
"""

from __future__ import annotations

import statistics

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import still_signed_in
from app.core.inventory_access import enrollment_of, require_inventory_volunteer, supervised_section_ids
from app.core.org_access import OrgAccess, org_access, require_org_admin
from app.core.orm import commit_and_refresh, release_before_waiting
from app.core.photos import (
    ALLOWED_CONTENT_TYPE,
    FIRST_PHOTO_INDEX,
    JPEG_MAGIC,
    MAX_PHOTO_BYTES,
    PHOTO_URL_TTL_SECONDS,
    PhotoStorageUnavailable,
    discard_refused_upload,
    inventory_photo_key,
    photo_storage_configured,
    photo_uploads_enabled,
    presigned_object_url,
    store_photo_object,
)
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
from app.routers.reports import read_capped_body, refuse_an_out_of_sequence_photo
from app.schemas.inventory import (
    EnrollmentCreate,
    EnrollmentOut,
    EnrollmentPatch,
    InventoryPhotoReceipt,
    InventorySettingsIn,
    InventorySettingsOut,
    ObservationCreate,
    ObservationReceipt,
)
from app.schemas.report import ReportPhotoLink

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


def _middle_of(readings: list) -> tuple[float, float, float]:
    """The point a record saves, and its accuracy, derived from its readings.

    Rule 2: the phone records what it knows and saves the middle of it. The
    middle is the median latitude and the median longitude taken separately
    - which a stray reading cannot drag, where a mean would follow it - and
    the accuracy is the median of the readings' own. Reasoned rather than
    measured: no real phone's readings under canopy have been looked at yet
    (#1997 — Where is it? — GPS readings populate a plain grid as they
    arrive, the median is saved with its accuracy and count, and the screen
    never shows a presumed place). The Location screen must show the point
    and accuracy this function computes, so its verdict and the saved record
    agree.
    """
    return (
        statistics.median(reading.lat for reading in readings),
        statistics.median(reading.lon for reading in readings),
        statistics.median(reading.acc for reading in readings),
    )


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


def _structure_for(
    db: Session, payload: ObservationCreate, enrollment: InventoryEnrollment, lat: float, lon: float
) -> InventoryStructure:
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
            lat=lat,
            lon=lon,
            created_by=enrollment.person_id,
        )
        db.add(structure)
        # Flushed now: these models declare no relationships, so nothing else
        # tells the session to insert the structure before the record on it.
        db.flush()
        return structure
    if structure.club_id != enrollment.club_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That structure id is already taken")
    # Followed to the end however long the chain, with each structure seen
    # once: a chain that comes back to itself is a loop somebody made by hand,
    # and one whose target is gone has nowhere to land. Both are refused
    # rather than followed forever or dereferenced into a 500.
    seen = {structure.id}
    while structure.status == StructureStatus.merged and structure.merged_into_id is not None:
        if structure.merged_into_id in seen:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That structure's merges loop back on themselves")
        target = db.get(InventoryStructure, structure.merged_into_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That structure was merged into one that is no longer in the inventory",
            )
        seen.add(target.id)
        structure = target
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
    `condition`, and the email to the club's admins is the job of #1992 —
    An Unsafe observation sends the Local Chair one email when mail is on, and nothing else.
    """
    observation_id = str(payload.id)
    existing = _already_uploaded(db, observation_id, enrollment)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _receipt(existing)

    lat, lon, accuracy_m = _middle_of(payload.readings)
    structure = _structure_for(db, payload, enrollment, lat, lon)

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
        lat=lat,
        lon=lon,
        accuracy_m=accuracy_m,
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
        size_bucket=payload.size_bucket.value if payload.size_bucket is not None else None,
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


# --- A record's photos ------------------------------------------------------
#
# #1986 — Observation photos use the report pipeline with a key of their own and no table.
#
# The report pipeline's, with a key of its own and no table: the same caps,
# the same JPEG check by header and by magic bytes, the same order - check,
# hand the database connection back, read the bytes, put them, then record
# them in one short transaction on the locked row - for the same reasons
# app/routers/reports.py argues at `_record_stored_photo`: #1915 — A photo upload holds a pooled database connection inside an open transaction while the phone sends the bytes, so fifteen slow uploads make every other read 500,
# and #1925 — Hand the database connection back before a photo upload waits for its bytes.
# Photos are numbered from FIRST_PHOTO_INDEX and the set is dense: an upload
# may append or replace, never skip, so `photo_count` always says how far
# `inventory/{id}/{n}.jpg` runs.


def _photo_target(row: InventoryObservation | None, index: int, club_id: str, person_id: str) -> InventoryObservation:
    """The record photo `index` may be written to, or the refusal that says why.

    404 for a record that is not the caller's at this club, uniformly: survey
    records are club-private, and a 403 would confirm an id names one.
    """
    if row is None or row.club_id != club_id or row.volunteer_id != person_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such record of yours")
    if not photo_uploads_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured on this server.",
        )
    refuse_an_out_of_sequence_photo(index, row.photo_count, "record")
    return row


def _photo_checked_then_released(
    db: Session, observation_id: str, index: int, enrollment: InventoryEnrollment
) -> tuple[str, str]:
    """The checks, then the connection handed back before the wait for the
    bytes; the caller's club and id as plain strings, read before the release
    so nothing afterwards touches an expired row."""
    club_id, person_id = enrollment.club_id, enrollment.person_id
    _photo_target(db.get(InventoryObservation, observation_id), index, club_id, person_id)
    release_before_waiting(db)
    return club_id, person_id


def _store_then_record_photo(
    db: Session, observation_id: str, index: int, body: bytes, club_id: str, person_id: str
) -> InventoryPhotoReceipt:
    """The put, holding no connection, then the record on the locked row.

    A refusal at the record step takes the object back out, unless a
    recorded photo is still using that key: a refused upload at an index
    already in the set has overwritten that photo, and deleting it would
    leave the count pointing at nothing.
    """
    key = inventory_photo_key(observation_id, index)
    try:
        store_photo_object(key, body)
    except PhotoStorageUnavailable as error:
        # `error.detail`, never `str(error)`: the message names the endpoint,
        # and the endpoint names the account (app/core/photos.py).
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error.detail) from error

    row = db.get(InventoryObservation, observation_id, with_for_update=True, populate_existing=True)
    try:
        still_signed_in(db, person_id)
        _photo_target(row, index, club_id, person_id)
    except HTTPException:
        unrecorded = row is None or index > row.photo_count
        db.rollback()
        if unrecorded:
            discard_refused_upload(key)
        raise
    # max(), not +1: an index inside the set is a retry or a replacement.
    row.photo_count = max(row.photo_count, index)
    commit_and_refresh(db, row)
    return InventoryPhotoReceipt(observation_id=row.id, photo_count=row.photo_count)


@router.put(
    "/clubs/{slug}/inventory/observations/{observation_id}/photos/{index}",
    response_model=InventoryPhotoReceipt,
    responses={
        404: {"description": "No such record of yours at this organization."},
        409: {"description": "That index is out of sequence, or past the cap."},
        413: {"description": "Photo is larger than the cap."},
        415: {"description": "Not a JPEG, by header or by magic bytes."},
        503: {"description": "This deployment has no photo bucket configured."},
    },
)
async def upload_inventory_photo(
    observation_id: str,
    index: int,
    request: Request,
    enrollment: InventoryEnrollment = Depends(require_inventory_volunteer),
    db: Session = Depends(get_db),
) -> InventoryPhotoReceipt:
    """Photo `index` of the caller's own record, numbered by the caller.

    The outbox re-sends photo 2 as photo 2, so a retry lands on the object it
    landed on last time. Words upload before photos (rule 4): a record's
    photos are sent only after the record itself has been answered.
    """
    club_id, person_id = await run_in_threadpool(_photo_checked_then_released, db, observation_id, index, enrollment)

    if (request.headers.get("content-type") or "").split(";")[0].strip() != ALLOWED_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Record photos must be {ALLOWED_CONTENT_TYPE}.",
        )
    body = await read_capped_body(request, MAX_PHOTO_BYTES)
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No photo in the request body.")
    if not body.startswith(JPEG_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Record photos must be {ALLOWED_CONTENT_TYPE}.",
        )
    return await run_in_threadpool(_store_then_record_photo, db, observation_id, index, body, club_id, person_id)


@router.get(
    "/clubs/{slug}/inventory/observations/{observation_id}/photos/{index}/link",
    response_model=ReportPhotoLink,
    responses={
        404: {"description": "No such record, no photo at that index, or not one you may see."},
        503: {"description": "This deployment has no photo bucket configured."},
    },
)
def get_inventory_photo_link(
    observation_id: str,
    index: int,
    response: Response,
    access: OrgAccess = Depends(org_access),
    db: Session = Depends(get_db),
) -> ReportPhotoLink:
    """A short-lived URL for one of a record's photos, `PHOTO_URL_TTL_SECONDS`.

    **Who may see it:** the volunteer who took it, the club's admins, and a
    section supervisor for a structure in a section under their role - the
    people who review it. Other volunteers browsing the inventory are the
    inventory screens' question, #2007 — Inventory and history: worst first, a history per structure, the Chair's note, CSV and GeoJSON - not this one's.

    **404 for everything it refuses**, the report link's rule: a distinct 403
    would confirm that an id names a real record to somebody who may not see
    it.
    """
    if not photo_storage_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured on this server.",
        )
    row = db.get(InventoryObservation, observation_id)
    refused = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record photo not found")
    if row is None or row.club_id != access.club.id or not FIRST_PHOTO_INDEX <= index <= row.photo_count:
        raise refused
    if row.volunteer_id != access.person_id and not access.is_admin:
        section_id = db.get(InventoryStructure, row.structure_id).section_id
        if not (
            access.is_supervisor
            and section_id is not None
            and section_id in supervised_section_ids(db, access.club.id, access.person_id)
        ):
            raise refused
    try:
        url = presigned_object_url(inventory_photo_key(row.id, index))
    except PhotoStorageUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error.detail) from error
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return ReportPhotoLink(url=url, expires_in=PHOTO_URL_TTL_SECONDS)
