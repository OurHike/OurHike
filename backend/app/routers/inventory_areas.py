"""`/clubs/{slug}/inventory/areas` and `/claims` - where a walk is needed.

#1988 — Priority areas are sections scored by the records in them, and a
claim is a day a volunteer means to walk one. features/STRUCTURE_INVENTORY.md
is the design. The maintainer decided by poll on 2026-11-04 that an area is
one of the club's own sections in v1 (the design doc's conflict 2).

**Who.** The design's permissions table puts "see priority areas, claim a
day" with the survey's volunteer: enrolled at the club, with the field
guide finished (`require_inventory_volunteer`). Nobody else reaches either
endpoint, including the club's admins unless they are enrolled too.

**What a section's answer is made of.** An observation belongs to a section
through its structure's `section_id`. Until #1987's placement fills that in
(The server computes an observation's mile and distance to the line from the
club's own section geometry, and stores both beside the raw point), no
structure has a section. So on real data every section reads
`none_in_a_year` until then. That is honest: no record is known to be in
it.

**A claim is a heads-up, not a lock.** It reserves nothing and nobody is
told when it lapses. The query decides what is current; nothing expires a
row (`app/models/inventory.py`'s `InventoryClaim`).

**Nothing here notifies anybody** (client/src/test/noNotifications.test.ts).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.inventory_access import require_inventory_volunteer
from app.core.orm import commit_and_refresh
from app.core.time import utc_now
from app.db.session import get_db
from app.models.inventory import (
    COVERAGE_MIN_RECORDS,
    COVERAGE_WINDOW_DAYS,
    MAX_CLAIM_DAYS_AHEAD,
    STALE_DAYS,
    InventoryClaim,
    InventoryClubSettings,
    InventoryEnrollment,
    InventoryObservation,
    InventoryStructure,
    ReviewState,
)
from app.models.org_registry import OrgPark, OrgSection, OrgTrail
from app.schemas.inventory_areas import AreaClaimOut, AreaOut, ClaimCreate, ClaimOut, Need

router = APIRouter(tags=["inventory"])

# Which records count toward a section's coverage. This is the design doc's
# open question 11, still the maintainer's to answer. The answer here is
# Reasoned, and it is in one place so it can be changed in one line.
#
# Every state except `not_ours`. The question names a cost on each side:
# - Counting only accepted records makes a slow review queue paint walked
#   sections as needing a walk.
# - Counting everything lets a record the Local Chair later marks "not ours"
#   hide a gap.
# Leaving out exactly `not_ours` avoids both. A submitted record counts the
# moment it uploads. A record stops counting the moment the Chair says it is
# not this club's. `returned` (sent back for a fix) and `merged` (its
# structure joined to another) are still a visit somebody made, so they
# count.
COUNTED_REVIEW_STATES = frozenset(set(ReviewState) - {ReviewState.not_ours})

# How far before the server's UTC date a claim's day may fall and still be
# "today". Reasoned: the backend knows no volunteer's time zone. Every US time
# zone is between UTC−4 and UTC−10, so the UTC date runs at most one day ahead
# of a US volunteer's own date. Without this, a volunteer claiming "today" after
# 8 pm Eastern would be refused for picking a day in the past, and their claim
# would vanish from the map the moment they made it. The cost of the slack is
# that a claim stays on the map for up to one day after its own date. A claim
# reserves nothing, so that is the cheap side to err on.
CLAIM_DAY_SLACK = 1


def _today() -> date:
    return utc_now().date()


def _earliest_current_day() -> date:
    return _today() - timedelta(days=CLAIM_DAY_SLACK)


def _first_name(typed_name: str | None) -> str | None:
    words = (typed_name or "").split()
    return words[0] if words else None


def _settings(db: Session, club_id: str) -> tuple[int, int, int, int]:
    """(claim_days_ahead, coverage_window_days, coverage_min_records, stale_days)."""
    row = db.get(InventoryClubSettings, club_id)
    if row is None:
        return MAX_CLAIM_DAYS_AHEAD, COVERAGE_WINDOW_DAYS, COVERAGE_MIN_RECORDS, STALE_DAYS
    return row.claim_days_ahead, row.coverage_window_days, row.coverage_min_records, row.stale_days


def _clubs_section(db: Session, club_id: str, section_id: str) -> OrgSection:
    section = (
        db.query(OrgSection)
        .join(OrgTrail, OrgTrail.id == OrgSection.trail_id)
        .join(OrgPark, OrgPark.id == OrgTrail.park_id)
        .filter(OrgSection.id == section_id, OrgPark.club_id == club_id)
        .one_or_none()
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such section at this organization")
    return section


def need_of(records_in_window: int, last_record_at: datetime | None, now: datetime, min_records: int, stale_days: int) -> Need:
    """Worst first. A section with nothing in `stale_days` days is the top priority
    whatever its window count, so a club that sets a window longer than its stale
    days still sees the stale ones first."""
    if last_record_at is None or last_record_at < now - timedelta(days=stale_days):
        return "none_in_a_year"
    if records_in_window < min_records:
        return "under_3_in_90"
    return "covered"


def _counted(db: Session, club_id: str, section_ids: Iterable[str]):
    return (
        db.query(InventoryStructure.section_id)
        .join(InventoryObservation, InventoryObservation.structure_id == InventoryStructure.id)
        .filter(
            InventoryStructure.club_id == club_id,
            InventoryStructure.section_id.in_(list(section_ids)),
            InventoryObservation.review_state.in_(COUNTED_REVIEW_STATES),
        )
    )


@router.get("/clubs/{slug}/inventory/areas", response_model=list[AreaOut])
def list_inventory_areas(
    trail: str = Query(..., description="The org trail whose sections to score"),
    enrollment: InventoryEnrollment = Depends(require_inventory_volunteer),
    db: Session = Depends(get_db),
) -> list[AreaOut]:
    """Each section of one of the club's trails, and how much it needs a walk.

    Sections come in trail order: by `start_mile`, with sections that have
    no mile last, then by name. The phone sorts by its own measure (nearest
    first, in the handoff's PickStretch screen).

    `records_90d` counts a record by its `captured_at`, the phone's clock at
    the moment of the visit. That is when the walk happened, which an upload
    time is not: an offline record can upload days later. A phone whose clock
    is wrong puts its record in the wrong window. Nothing here corrects it.
    """
    club_id = enrollment.club_id
    found = (
        db.query(OrgTrail.id)
        .join(OrgPark, OrgPark.id == OrgTrail.park_id)
        .filter(OrgTrail.id == trail, OrgPark.club_id == club_id)
        .one_or_none()
    )
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such trail at this organization")

    sections = (
        db.query(OrgSection)
        .filter(OrgSection.trail_id == trail)
        .order_by(OrgSection.start_mile.is_(None), OrgSection.start_mile, OrgSection.name)
        .all()
    )
    ids = [section.id for section in sections]
    _, window_days, min_records, stale_days = _settings(db, club_id)
    now = utc_now()

    latest = dict(
        _counted(db, club_id, ids)
        .with_entities(InventoryStructure.section_id, func.max(InventoryObservation.captured_at))
        .group_by(InventoryStructure.section_id)
        .all()
    )
    in_window = dict(
        _counted(db, club_id, ids)
        .filter(InventoryObservation.captured_at >= now - timedelta(days=window_days))
        .with_entities(InventoryStructure.section_id, func.count(InventoryObservation.id))
        .group_by(InventoryStructure.section_id)
        .all()
    )

    claims: dict[str, list[AreaClaimOut]] = {section_id: [] for section_id in ids}
    rows = (
        db.query(InventoryClaim, InventoryEnrollment.typed_name)
        .outerjoin(
            InventoryEnrollment,
            (InventoryEnrollment.club_id == InventoryClaim.club_id)
            & (InventoryEnrollment.person_id == InventoryClaim.volunteer_id),
        )
        .filter(
            InventoryClaim.club_id == club_id,
            InventoryClaim.section_id.in_(ids),
            InventoryClaim.released_at.is_(None),
            InventoryClaim.walk_on >= _earliest_current_day(),
        )
        .order_by(InventoryClaim.walk_on, InventoryClaim.claimed_at)
        .all()
    )
    for claim, typed_name in rows:
        mine = claim.volunteer_id == enrollment.person_id
        claims[claim.section_id].append(
            AreaClaimOut(walk_on=claim.walk_on, first_name=_first_name(typed_name), mine=mine, id=claim.id if mine else None)
        )

    return [
        AreaOut(
            section_id=section.id,
            name=section.name,
            start_anchor=section.start_anchor,
            end_anchor=section.end_anchor,
            miles=section.miles,
            records_90d=in_window.get(section.id, 0),
            last_record_at=latest.get(section.id),
            need=need_of(in_window.get(section.id, 0), latest.get(section.id), now, min_records, stale_days),
            claims=claims[section.id],
        )
        for section in sections
    ]


@router.post("/clubs/{slug}/inventory/claims", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def claim_a_day(
    payload: ClaimCreate,
    response: Response,
    enrollment: InventoryEnrollment = Depends(require_inventory_volunteer),
    db: Session = Depends(get_db),
) -> InventoryClaim:
    """Say you mean to walk a section on a day, up to the club's `claim_days_ahead`.

    Claiming the same section for the same day twice answers the first claim
    with 200 and writes nothing, so a retried request is not a second claim.
    Other volunteers' claims never refuse yours: two people walking one
    section on one day is two sets of records.
    """
    club_id = enrollment.club_id
    section = _clubs_section(db, club_id, payload.section_id)
    days_ahead, *_ = _settings(db, club_id)
    if payload.walk_on < _earliest_current_day():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="That day has already passed")
    last = _today() + timedelta(days=days_ahead)
    if payload.walk_on > last:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A claim can be at most {days_ahead} days ahead, so {last.isoformat()} at the latest",
        )

    existing = (
        db.query(InventoryClaim)
        .filter(
            InventoryClaim.club_id == club_id,
            InventoryClaim.volunteer_id == enrollment.person_id,
            InventoryClaim.section_id == section.id,
            InventoryClaim.walk_on == payload.walk_on,
            InventoryClaim.released_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    claim = InventoryClaim(club_id=club_id, volunteer_id=enrollment.person_id, section_id=section.id, walk_on=payload.walk_on)
    db.add(claim)
    return commit_and_refresh(db, claim)


@router.delete("/clubs/{slug}/inventory/claims/{claim_id}", status_code=status.HTTP_204_NO_CONTENT)
def release_a_claim(
    claim_id: str,
    enrollment: InventoryEnrollment = Depends(require_inventory_volunteer),
    db: Session = Depends(get_db),
) -> Response:
    """Take your claim back. The row stays, with `released_at` set.

    Only the volunteer who made a claim can release it. Anybody else's claim
    answers the same 404 as a claim that does not exist, so the endpoint
    cannot be used to find out which ids are real. Releasing twice is not an
    error.
    """
    claim = (
        db.query(InventoryClaim)
        .filter(
            InventoryClaim.id == claim_id,
            InventoryClaim.club_id == enrollment.club_id,
            InventoryClaim.volunteer_id == enrollment.person_id,
        )
        .one_or_none()
    )
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such claim of yours")
    if claim.released_at is None:
        claim.released_at = utc_now()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
