"""Each club's ranking weights, with every change kept (PLAN.md §8 `club_weights`).

Decided by poll (2026-10-26): anyone signed in may change any club's weights,
and the history makes every change visible and undoable. PLAN.md §10 "Open
weights" names what that leaves open. What this file adds is only what keeps
the history worth reading: the club must be one the analysis knows, a change
must change something, and one account makes at most
limits.WEIGHT_CHANGES_PER_DAY of them a day.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from steward_api import limits
from steward_api.auth import current_user
from steward_api.clubs import ClubDirectory, ClubsUnavailable
from steward_api.db import get_db
from steward_api.models import ClubWeights, StewardUser
from steward_api.schemas import ClubWeightsView, WeightsChange, WeightsEntry, WeightsRestore

router = APIRouter(prefix="/weights", tags=["weights"])

#: History entries returned, newest first. A club past this many changes has
#: a history nobody reads in full; the older rows stay in the table.
HISTORY_LIMIT = 50


def _values(row: ClubWeights) -> dict[str, int]:
    return {name: getattr(row, name) for name in limits.WEIGHT_NAMES}


def _entry(row: ClubWeights, names: dict[str, str | None], user: StewardUser) -> WeightsEntry:
    return WeightsEntry(
        id=row.id,
        **_values(row),
        note=row.note,
        restored_from=row.restored_from,
        changed_by=names.get(row.changed_by) if row.changed_by else None,
        by_you=row.changed_by == user.id,
        changed_at=row.changed_at,
    )


def _view(db: Session, club: str, user: StewardUser) -> ClubWeightsView:
    rows = db.scalars(
        select(ClubWeights)
        .where(ClubWeights.club == club)
        .order_by(ClubWeights.changed_at.desc(), ClubWeights.id.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    people = {row.changed_by for row in rows if row.changed_by}
    names = dict(db.execute(select(StewardUser.id, StewardUser.display_name).where(StewardUser.id.in_(people))).all())
    return ClubWeightsView(
        club=club,
        current=_values(rows[0]) if rows else dict(limits.DEFAULT_WEIGHTS),
        defaults=dict(limits.DEFAULT_WEIGHTS),
        history=[_entry(row, names, user) for row in rows],
    )


def _known_club(request: Request, club: str) -> None:
    directory: ClubDirectory = request.app.state.clubs
    try:
        known = directory.names()
    except ClubsUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The club list cannot be read right now, so no change can be checked"
        ) from exc
    if club not in known:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No club by that name in the latest analysis")


def _under_daily_cap(db: Session, user: StewardUser) -> None:
    since = datetime.now(UTC) - timedelta(days=1)
    made = db.scalar(
        select(func.count()).select_from(ClubWeights).where(ClubWeights.changed_by == user.id, ClubWeights.changed_at >= since)
    )
    if (made or 0) >= limits.WEIGHT_CHANGES_PER_DAY:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, f"One account can change weights {limits.WEIGHT_CHANGES_PER_DAY} times a day"
        )


def _current(db: Session, club: str) -> dict[str, int]:
    row = db.scalars(
        select(ClubWeights)
        .where(ClubWeights.club == club)
        .order_by(ClubWeights.changed_at.desc(), ClubWeights.id.desc())
        .limit(1)
    ).first()
    return _values(row) if row else dict(limits.DEFAULT_WEIGHTS)


@router.get("", response_model=ClubWeightsView)
def read_weights(
    club: str = Query(min_length=1, max_length=limits.CLUB_MAX),
    user: StewardUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> ClubWeightsView:
    return _view(db, club, user)


@router.post("", response_model=ClubWeightsView, status_code=status.HTTP_201_CREATED)
def change_weights(
    body: WeightsChange, request: Request, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)
) -> ClubWeightsView:
    _known_club(request, body.club)
    values = body.model_dump(include=set(limits.WEIGHT_NAMES))
    if values == _current(db, body.club):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "These are already the club's weights")
    _under_daily_cap(db, user)
    db.add(ClubWeights(club=body.club, **values, note=body.note, changed_by=user.id))
    db.commit()
    return _view(db, body.club, user)


@router.post("/{entry_id}/restore", response_model=ClubWeightsView, status_code=status.HTTP_201_CREATED)
def restore_weights(
    entry_id: int,
    body: WeightsRestore,
    request: Request,
    user: StewardUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> ClubWeightsView:
    """Undo: a new entry with an earlier entry's weights, pointing back at it."""
    earlier = db.get(ClubWeights, entry_id)
    if earlier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such weights entry")
    _known_club(request, earlier.club)
    if _values(earlier) == _current(db, earlier.club):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "These are already the club's weights")
    _under_daily_cap(db, user)
    db.add(ClubWeights(club=earlier.club, **_values(earlier), note=body.note, restored_from=earlier.id, changed_by=user.id))
    db.commit()
    return _view(db, earlier.club, user)
