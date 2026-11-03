"""`/ridge-runner` - a volunteer trail monitor's own commitment window.

features/VOLUNTEERING.md §3 and #763. `app/models/ridge_runner.py` carries
why the name is qualified wherever a third party can see it, and why the
seven-day cap is the whole guardrail.

**Every read here is the caller's own.** There is no list endpoint, no
per-organization view and nothing public - the role is a mode the app is in,
visible to its user and to the organization receiving the data, and to nobody
else. **The app issues nothing that functions as a badge**, which is a safety
rule rather than a product one: a hiker who believes they are talking to an
ATC Ridgerunner may take instructions from a volunteer with no authority to
give them.

**There is no completion anywhere in this file.** No percentage, no days
kept, no streak. A window that ends cannot become an obligation that
accumulates, and the record shows what was submitted rather than what was
expected and missed.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.orm import commit_and_refresh
from app.core.time import utc_now
from app.db.session import get_db
from app.models.profile import Profile
from app.models.ridge_runner import RidgeRunnerCommitment
from app.schemas.ridge_runner import CommitmentCreate, CommitmentOut

router = APIRouter(prefix="/ridge-runner", tags=["ridge-runner"])


@router.get("/mine", response_model=list[CommitmentOut])
def list_my_commitments(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RidgeRunnerCommitment]:
    """Every window this person has opened, newest first."""
    return (
        db.query(RidgeRunnerCommitment)
        .filter(RidgeRunnerCommitment.person_id == current_user.id)
        .order_by(RidgeRunnerCommitment.starts_on.desc())
        .all()
    )


@router.post("", response_model=CommitmentOut, status_code=status.HTTP_201_CREATED)
def open_commitment(
    payload: CommitmentCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RidgeRunnerCommitment:
    """Open a window, up to seven days.

    **One at a time.** Overlapping windows would be a way to build a chain of
    them - open the next before the last ends, and the cap stops capping
    anything. The refusal names the open one rather than saying "no", so the
    answer is actionable.

    The seven-day check lives in the schema and is repeated by nothing here,
    because a rule enforced in two places is a rule that gets changed in one.
    """
    overlapping = (
        db.query(RidgeRunnerCommitment)
        .filter(
            RidgeRunnerCommitment.person_id == current_user.id,
            RidgeRunnerCommitment.ended_early_at.is_(None),
            RidgeRunnerCommitment.ends_on >= payload.starts_on,
            RidgeRunnerCommitment.starts_on <= payload.ends_on,
        )
        .first()
    )
    if overlapping is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You already have a window open until {overlapping.ends_on.isoformat()}. "
                "Close it first, or start the new one after it."
            ),
        )

    commitment = RidgeRunnerCommitment(
        person_id=current_user.id,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        tasks=",".join(payload.tasks),
        club_id=payload.club_id,
        note=payload.note,
    )
    db.add(commitment)
    return commit_and_refresh(db, commitment)


@router.post("/{commitment_id}/close", response_model=CommitmentOut)
def close_commitment(
    commitment_id: str,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RidgeRunnerCommitment:
    """Close a window early. It records that it ended, and nothing else.

    No confirmation, no "are you sure you want to give up", and no field
    anywhere saying how much of the window was used. A partial week is a
    week's worth of real work and the app says so in exactly those terms.
    """
    commitment = (
        db.query(RidgeRunnerCommitment)
        .filter(
            RidgeRunnerCommitment.id == commitment_id,
            RidgeRunnerCommitment.person_id == current_user.id,
        )
        .one_or_none()
    )
    if commitment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such commitment of yours")

    if commitment.ended_early_at is None:
        commitment.ended_early_at = utc_now()
        # The window is over, so its end date is today rather than a date in
        # the future that would keep the app in monitor mode.
        commitment.ends_on = min(commitment.ends_on, date.today())
    return commit_and_refresh(db, commitment)
