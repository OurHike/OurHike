"""`/field-notes` endpoints - dated observations about a place.

See ../../../features/FIELD_NOTES.md. Browsing (`GET`) needs no account,
matching every other browsing endpoint; writing (`POST`) requires a real
identity, because §4's corroboration rule counts *distinct accounts* and an
anonymous note cannot be counted, rate-limited, or hidden as part of a
pattern.

The moderation posture is the reverse of reports', argued in §5: a note is
visible the moment it lands, and moderators see only what is flagged. The
flag-and-hide endpoints at the bottom are that surface - and they also
answer SAYING_THANKS.md's deferred "abuse handling specifics", which asked
for exactly this shape and wanted it built once.
"""

import enum
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, get_current_user_optional, require_role
from app.core.orm import commit_and_refresh, get_or_404
from app.core.time import to_naive_utc, utc_now
from app.db.session import get_db
from app.models.field_note import FieldNote, NoteFlag
from app.models.profile import MODERATOR_ROLES, Profile
from app.schemas.field_note import (
    FieldNoteCreate,
    FieldNoteOut,
    FlaggedNoteOut,
    NoteFlagCreate,
)

router = APIRouter(tags=["field-notes"])

# How far back the unfiltered list reaches, and how many notes per place it
# carries. These mirror the bake's own bounds (pipeline/export_conditions.py)
# because the live read and the baseline must be the same document from two
# doors - an artifact that grows without bound is a download that eventually
# fails on the trail, and a live list with no bound is the same failure with
# a spinner in front of it.
#
# @unvalidated - both numbers. FIELD_NOTES.md's own open question: "K, and
# the time window... A number with a download size on one side and an
# offline hiker's context on the other; measurable once there is volume,
# guessable only badly before then." 90 days spans a season and 5 notes
# outlasts a contested weekend; what would settle them is real note volume
# per POI once hikers are writing any.
NOTES_WINDOW_DAYS = 90
NOTES_PER_POI = 5

# A card wants the place's whole recent story, not the map's cap - but still
# bounded, because "the full history is a live-only read" must not mean "an
# unbounded response" (same 50 MB reasoning as schemas/common.NoteText).
NOTES_PER_POI_DETAIL = 50


def _already_filed(db: Session, note_id: str, current_user: Profile) -> FieldNote | None:
    """The caller's own note under this id, if it is already stored.

    Same contract and same refusal as reports' `_already_filed`: a row
    belonging to somebody else raises rather than returns, so a guessed UUID
    is not a way to read another person's note (with its reporter_id) back.
    """
    existing = db.get(FieldNote, note_id)
    if existing is None:
        return None
    if existing.reporter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That note id belongs to someone else.",
        )
    return existing


@router.post("/field-notes", response_model=FieldNoteOut, status_code=status.HTTP_201_CREATED)
def create_field_note(
    payload: FieldNoteCreate,
    response: Response,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FieldNoteOut:
    """File a note. Visible to every reader the moment this returns - the
    publish-now decision FIELD_NOTES.md §5 argues, not an oversight.

    Idempotent on `id`, exactly as `POST /reports` is (#243): re-sending a
    note that already arrived returns the stored one with `200` instead of
    filing a second copy, because the outbox's ordinary path is a send whose
    response never came back.
    """
    note_id = str(payload.id) if payload.id is not None else None

    if note_id is not None:
        settled = _already_filed(db, note_id, current_user)
        if settled is not None:
            response.status_code = status.HTTP_200_OK
            return FieldNoteOut.for_viewer(settled, current_user)

    now = utc_now()
    observed = to_naive_utc(payload.observed_at)

    note = FieldNote(
        **({"id": note_id} if note_id is not None else {}),
        reporter_id=current_user.id,
        poi_id=payload.poi_id,
        lat=payload.lat,
        lon=payload.lon,
        mile=payload.mile,
        observation=payload.observation,
        note=payload.note,
        observed_at=observed if observed is not None else now,
        posted_at=now,
        reporter_type=payload.reporter_type,
    )
    db.add(note)
    try:
        return FieldNoteOut.for_viewer(commit_and_refresh(db, note), current_user)
    except IntegrityError:
        # Two concurrent sends of the same id both saw "not filed yet" - the
        # exact race the retry path exists to produce (#265's lesson, applied
        # here from the start rather than after the 500).
        db.rollback()
        settled = _already_filed(db, note_id, current_user) if note_id is not None else None
        if settled is None:
            raise
        response.status_code = status.HTTP_200_OK
        return FieldNoteOut.for_viewer(settled, current_user)


@router.get("/field-notes", response_model=list[FieldNoteOut])
def list_field_notes(
    poi_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: Profile | None = Depends(get_current_user_optional),
) -> list[FieldNoteOut]:
    """Visible notes, newest observation first.

    With `poi_id`: that place's recent story, for the card. Without: the
    map's working set - every place's most recent few inside the window,
    which is what the client rolls `last_confirmed_at` up from at render
    time (derive-don't-duplicate, FIELD_NOTES.md §3).

    Hidden notes are excluded for every caller, the author included. Unlike
    a submitted report - which has a "waiting" state its author watches - a
    hidden note has been removed by a person, and continuing to render it to
    its author would show them a map nobody else is seeing. Moderators read
    hidden notes through their own queue below, where hiding is reviewable
    and reversible.

    Ordering by `observed_at` leaks nothing the rows don't already say -
    every row carries it - which is why this list may be meaningfully
    ordered where `GET /reports` deliberately is not (see its comment on
    array order as a covert clock).
    """
    visible = FieldNote.hidden_at.is_(None)

    if poi_id is not None:
        rows = (
            db.query(FieldNote)
            .filter(visible, FieldNote.poi_id == poi_id)
            .order_by(FieldNote.observed_at.desc(), FieldNote.id)
            .limit(NOTES_PER_POI_DETAIL)
            .all()
        )
        return [FieldNoteOut.for_viewer(row, current_user) for row in rows]

    cutoff = utc_now() - timedelta(days=NOTES_WINDOW_DAYS)
    # Each place's most recent K. Notes with no poi_id get a partition each
    # (coalesced onto their own id) rather than sharing one bucket - they are
    # pin-less anchor notes, and five of them TOTAL would be a cap on the
    # wrong thing.
    ranked = (
        db.query(
            FieldNote.id.label("note_id"),
            func.row_number()
            .over(
                partition_by=func.coalesce(FieldNote.poi_id, FieldNote.id),
                order_by=(FieldNote.observed_at.desc(), FieldNote.id),
            )
            .label("recency_rank"),
        )
        .filter(visible, FieldNote.observed_at >= cutoff)
        .subquery()
    )
    rows = (
        db.query(FieldNote)
        .join(ranked, FieldNote.id == ranked.c.note_id)
        .filter(ranked.c.recency_rank <= NOTES_PER_POI)
        .order_by(FieldNote.observed_at.desc(), FieldNote.id)
        .all()
    )
    return [FieldNoteOut.for_viewer(row, current_user) for row in rows]


@router.post("/field-notes/{note_id}/flag", status_code=status.HTTP_201_CREATED)
def flag_field_note(
    note_id: str,
    payload: NoteFlagCreate,
    response: Response,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Ask for a moderator's eyes on a note.

    Auth required - a flag is testimony too, and an anonymous flood of them
    would be the cheapest way to get every note on a stretch pulled into the
    queue. One flag per account per note: flagging twice returns 200 and
    changes nothing, because the queue counts people, not taps.

    404 for a hidden note the same as for a missing one - it is already in
    front of a moderator, and distinguishing the two would confirm a removal
    to whoever caused it.
    """
    note = db.get(FieldNote, note_id)
    if note is None or note.hidden_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    existing = db.query(NoteFlag).filter(NoteFlag.note_id == note_id, NoteFlag.flagged_by == current_user.id).first()
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return {"status": "already flagged"}

    flag = NoteFlag(note_id=note_id, flagged_by=current_user.id, reason=payload.reason)
    db.add(flag)
    db.commit()
    return {"status": "flagged"}


class QueueScope(str, enum.Enum):
    """What the moderation list covers - see read_note_queue."""

    flagged = "flagged"
    hidden = "hidden"
    all = "all"


def _queue_entry(db: Session, note: FieldNote, viewer: Profile) -> FlaggedNoteOut:
    flags = db.query(NoteFlag).filter(NoteFlag.note_id == note.id).order_by(NoteFlag.created_at, NoteFlag.id).all()
    return FlaggedNoteOut(
        note=FieldNoteOut.for_viewer(note, viewer),
        flag_count=len(flags),
        reasons=[flag.reason for flag in flags if flag.reason is not None and flag.reason.strip() != ""],
        hidden=note.hidden_at is not None,
    )


@router.get("/moderation/field-notes", response_model=list[FlaggedNoteOut])
def read_note_queue(
    scope: QueueScope = QueueScope.all,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> list[FlaggedNoteOut]:
    """The notes needing or bearing a decision: flagged ones, and hidden ones.

    Flagged-and-visible is the work; hidden is the record, listed so a wrong
    removal is findable and reversible (§5: "a flagged note is hidden, never
    deleted, so a wrong removal is recoverable"). Most-flagged first within
    each, because three people saying so outranks one.
    """
    flagged_ids = db.query(NoteFlag.note_id).distinct()

    query = db.query(FieldNote)
    if scope is QueueScope.flagged:
        query = query.filter(FieldNote.hidden_at.is_(None), FieldNote.id.in_(flagged_ids))
    elif scope is QueueScope.hidden:
        query = query.filter(FieldNote.hidden_at.is_not(None))
    else:
        query = query.filter(FieldNote.hidden_at.is_not(None) | FieldNote.id.in_(flagged_ids))

    notes = query.all()
    entries = [_queue_entry(db, note, current_user) for note in notes]
    # Visible work before the archive of removals; most corroborated first;
    # id last so the order is deterministic under test.
    entries.sort(key=lambda entry: (entry.hidden, -entry.flag_count, entry.note.id))
    return entries


@router.post("/field-notes/{note_id}/hide", response_model=FlaggedNoteOut)
def hide_field_note(
    note_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> FlaggedNoteOut:
    """Remove a note from every public read and from the next bake.

    Latest-wins on the trail columns, the dismissal convention (#658): "who
    took this down" means the operative removal. The row is kept - see the
    model. The bake clears it from the published baseline within a day,
    which is the honest cost CONDITIONS_DELIVERY.md already accepts.
    """
    note = get_or_404(db, FieldNote, note_id, detail="Note not found")
    note.hidden_at = utc_now()
    note.hidden_by = current_user.id
    return _queue_entry(db, commit_and_refresh(db, note), current_user)


@router.post("/field-notes/{note_id}/unhide", response_model=FlaggedNoteOut)
def unhide_field_note(
    note_id: str,
    current_user: Profile = Depends(require_role(*MODERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> FlaggedNoteOut:
    """Put a wrongly-removed note back - the recoverability §5 promises.

    The flags stay: they are the record of why somebody looked, and a note
    unhidden over them reads in the queue as reviewed rather than as never
    questioned.
    """
    note = get_or_404(db, FieldNote, note_id, detail="Note not found")
    note.hidden_at = None
    note.hidden_by = None
    return _queue_entry(db, commit_and_refresh(db, note), current_user)
