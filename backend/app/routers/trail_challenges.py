"""Challenges - a club's list of places, a hiker's tags, and the finish (#1780 —
Let a club publish a challenge — places on its own trails that hikers opt into
and tag at camp — starting with the ATC's A.T. Summer Bucket List).

features/CHALLENGES.md is the design; this is its server half, "On the
server" there. Named `trail_challenges` because `challenge` already means
proof-of-work in this backend (app/core/challenge.py).

Two audiences, and they never see each other:

*A hiker* sends tags and, at the finish, one entry. Both come through the
phone's outbox, so both are idempotent on the client's own id - volunteer
hours' contract, verbatim: 201 the first time, 200 on a replay, 409 for an id
that is somebody else's.

*A club's admins* save the challenge's definition, read counts, and download
the finishers as a CSV. **Counts, never names**, except in that one file, and
only the names hikers typed into an entry and sent to this club on purpose.
A count below `CHALLENGE_COUNT_FLOOR` distinct hikers is withheld, because a
count of three in a club's own challenge describes three people the club may
know.

**A tag is refused only past a cap.** A tag after the window closes is
accepted, and so is a tag for a challenge no club has saved: the phone's
record is the hiker's, and a server that dropped a tag because the console had
not caught up would be deciding what the hiker did. The one refusal is
`TAGS_PER_HIKER_CAP`, because this server cannot tell a published challenge id
from an invented one. A hiker takes a tag back with the two DELETE routes. An
ENTRY after close is refused, with a sentence the phone shows as it is.

**WHO RECEIVES AN ENTRY.** Owning a challenge id is first come - the first
claimed organization to save it - and is not, on its own, who receives an
entry. The phone sends the web domain the published list names for its
publisher (pipeline/reference/challenges/publishers.json, through the
artifact's `org_domain`), and `send_entry` gives the entry only to a claimed
club that proved that domain. A publisher's org id is also held for its own
domain (app/core/trail_challenge.py's PUBLISHER_DOMAINS), so a squatter can
neither register `atc` nor save the ATC's ids.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_current_user
from app.core.org_access import OrgAccess, require_org_admin
from app.core.orm import commit_and_refresh
from app.core.registry_pr import RegistryPrRefused, open_challenge_pr
from app.core.time import to_naive_utc, utc_now
from app.core.trail_challenge import (
    CHALLENGE_COUNT_FLOOR,
    ID_MAX_CHARS,
    ID_PATTERN,
    closed_sentence,
    has_closed,
    may_publish_as,
    spreadsheet_safe,
)
from app.db.session import get_db
from app.models.club import Club, OrgState
from app.models.profile import Profile
from app.models.trail_challenge import ChallengeEntry, ChallengeTag, ClubChallenge, TagHow
from app.schemas.trail_challenge import (
    ChallengeCountsOut,
    ChallengeEntryCreate,
    ChallengeEntryOut,
    ChallengePublishOut,
    ChallengeTagCreate,
    ChallengeTagOut,
    ChallengeWindowOut,
    ClubChallengeOut,
    ClubChallengeSummary,
    ClubChallengeUpsert,
)

router = APIRouter(tags=["challenges"])

ChallengeIdPath = Annotated[str, Path(pattern=ID_PATTERN, max_length=ID_MAX_CHARS)]

# The refusals the phone shows verbatim - so they are sentences to a hiker,
# written once, and the tests hold them to the letter.
NOT_TAKING_ENTRIES = "This challenge's club is not taking entries through OurHike yet."
ALREADY_SENT = "You have already sent an entry for this challenge."

#: The largest definition a save takes, as JSON text. @unvalidated: about ten
#: times the ATC's reviewed file (26,327 bytes for 100 items, measured
#: 2026-09-30), so that no list a club writes by hand meets it and a script
#: posting megabytes into a column does. What would settle it: the largest
#: list a club actually publishes.
DEFINITION_MAX_CHARS = 262_144

#: How deeply a definition may nest. Reasoned: the reviewed file's deepest
#: path is items[].match.places[].<field>, five levels; twelve leaves room for
#: the shape to grow and none for a hostile one.
DEFINITION_MAX_DEPTH = 12

#: Saved challenges per organization. @unvalidated: the ATC publishes one a
#: year; 25 is room for a decade of drafts and a ceiling on how many branches
#: and pull requests one admin can open here. What would settle it: a club
#: that runs more.
CHALLENGES_PER_CLUB_CAP = 25

#: Tags one account may hold, across every challenge. @unvalidated: the ATC's
#: list has 100 items and a hiker might join a dozen lists; 2,000 is far past
#: that and stops a script filling the table under invented ids. What would
#: settle it: the most tags any real hiker holds.
TAGS_PER_HIKER_CAP = 2000

#: A definition's statuses, pipeline/lib/challenges.py's `STATUSES`.
DEFINITION_STATUSES = ("draft", "published")

#: The finishers' CSV, in column order. `hand_tagged_item_ids` is the club's
#: half of "the club decides what a hand tag is worth" (features/
#: CHALLENGES.md): which of the items an entry lists were tagged by hand
#: rather than by the day's GPS track.
CSV_COLUMNS = (
    "sent_at",
    "name",
    "email",
    "mailing_address",
    "item_count",
    "item_ids",
    "hand_tagged_item_ids",
    # Items the entry lists that this hiker never sent a tag for. Without it
    # an item reads as tagged from the walk by not appearing in the column
    # above - the one column a club reads to judge an entry.
    "untagged_item_ids",
    "finished_only",
)


# ------------------------------------------------------------------ #
# A hiker's tags
# ------------------------------------------------------------------ #


def _tag_out(db: Session, tag: ChallengeTag) -> ChallengeTagOut:
    return ChallengeTagOut(
        id=tag.id,
        challenge_id=tag.challenge_id,
        item_id=tag.item_id,
        how=tag.how,
        authored_at=tag.authored_at,
        received_at=tag.received_at,
    )


def _own_tag(db: Session, tag_id: str, current_user: Profile, payload: ChallengeTagCreate) -> ChallengeTag | None:
    """The caller's own tag under this id, None to proceed, and somebody
    else's id refused outright - reports' idempotency contract (#243)."""
    existing = db.get(ChallengeTag, tag_id)
    if existing is None:
        return None
    if existing.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That tag id belongs to someone else.")
    if (existing.challenge_id, existing.item_id) != (payload.challenge_id, payload.item_id):
        # One outbox id for two different places is a client bug, and
        # answering with the other place's tag would tell the phone this
        # one was recorded.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That tag id was sent for a different place.")
    return existing


def _same_place(db: Session, user_id: str, challenge_id: str, item_id: str) -> ChallengeTag | None:
    return (
        db.query(ChallengeTag)
        .filter(
            ChallengeTag.user_id == user_id,
            ChallengeTag.challenge_id == challenge_id,
            ChallengeTag.item_id == item_id,
        )
        .one_or_none()
    )


@router.post("/challenges/tags", response_model=ChallengeTagOut, status_code=status.HTTP_201_CREATED)
def tag_a_place(
    payload: ChallengeTagCreate,
    response: Response,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChallengeTagOut:
    """Record that the hiker tagged one item - accepted below the per-hiker cap.

    **Idempotent twice over.** On `id`, for the outbox: a flush that committed
    and lost its response resends the same id and gets the same row with 200.
    And on the place itself: the same item tagged again under a NEW id is the
    same hiker on a second device, which is the same fact arriving twice, not
    an error - the row already here comes back with 200, and the first tag to
    arrive stands, except that a walked tag upgrades a hand one.

    **Capped per hiker** at `TAGS_PER_HIKER_CAP`, because the server cannot
    tell a published challenge id from an invented one and stores both.
    """
    tag_id = str(payload.id)

    settled = _own_tag(db, tag_id, current_user, payload) or _same_place(
        db, current_user.id, payload.challenge_id, payload.item_id
    )
    if settled is not None:
        # A walk outranks a tap. The phone's hand tag arrived first and its
        # day's walk confirmed it later (or another device walked it): the
        # club's CSV should read walked, not hand.
        if settled.how == TagHow.hand and payload.how == TagHow.gps:
            settled.how = TagHow.gps
            commit_and_refresh(db, settled)
        response.status_code = status.HTTP_200_OK
        return _tag_out(db, settled)

    _one_at_a_time(db, f"challenge-tags:{current_user.id}")
    if db.query(func.count(ChallengeTag.id)).filter(ChallengeTag.user_id == current_user.id).scalar() >= TAGS_PER_HIKER_CAP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account has more challenge tags than any list could need, so this one was not kept.",
        )

    tag = ChallengeTag(
        id=tag_id,
        user_id=current_user.id,
        challenge_id=payload.challenge_id,
        item_id=payload.item_id,
        how=payload.how,
        # Stored naive-UTC (app/models/profile.py), converted rather than
        # truncated: a phone's `-04:00` is four hours, not nothing.
        authored_at=to_naive_utc(payload.authored_at),
        received_at=utc_now(),
    )
    db.add(tag)
    try:
        commit_and_refresh(db, tag)
    except IntegrityError:
        # The check above and this insert are two statements, and two devices
        # flushing at once is exactly what produces the interleaving - the
        # loser answers with the winner's row rather than a 500 (#265).
        db.rollback()
        settled = _own_tag(db, tag_id, current_user, payload) or _same_place(
            db, current_user.id, payload.challenge_id, payload.item_id
        )
        if settled is None:
            raise
        response.status_code = status.HTTP_200_OK
        return _tag_out(db, settled)
    return _tag_out(db, tag)


@router.delete("/challenges/{challenge_id}/items/{item_id}/tag", status_code=status.HTTP_204_NO_CONTENT)
def take_back_a_tag(
    challenge_id: ChallengeIdPath,
    item_id: ChallengeIdPath,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Take back the caller's own tag of one item - the phone's "Remove this
    tag", or a hand tag pressed twice, after it already left the phone.

    By place rather than by id, because the row here may carry the id of the
    hiker's other device (`tag_a_place` keeps the first to arrive). 204
    whether or not there was one: the outbox resends this until it lands, and
    "already gone" is the answer it wants.
    """
    db.query(ChallengeTag).filter(
        ChallengeTag.user_id == current_user.id,
        ChallengeTag.challenge_id == challenge_id,
        ChallengeTag.item_id == item_id,
    ).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/challenges/{challenge_id}/tags", status_code=status.HTTP_204_NO_CONTENT)
def leave_a_challenge(
    challenge_id: ChallengeIdPath,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Take back every one of the caller's tags on one challenge - Leave.

    A hiker who left is not one of the club's "Hikers in". Their tags stay on
    their phone, and rejoining sends them again. An entry already sent is not
    touched: that went to the club because the hiker sent it.
    """
    db.query(ChallengeTag).filter(
        ChallengeTag.user_id == current_user.id,
        ChallengeTag.challenge_id == challenge_id,
    ).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ #
# A hiker's entry
# ------------------------------------------------------------------ #


def _own_entry(db: Session, entry_id: str, current_user: Profile, challenge_id: str) -> ChallengeEntry | None:
    existing = db.get(ChallengeEntry, entry_id)
    if existing is None:
        return None
    if existing.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That entry id belongs to someone else.")
    if existing.challenge_id != challenge_id:
        # The same outbox id under a different challenge is a client bug, and
        # answering with an entry for some other challenge would tell the
        # phone this one was sent.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That entry id was sent for a different challenge.")
    return existing


def _entry_for(db: Session, user_id: str, challenge_id: str) -> ChallengeEntry | None:
    return (
        db.query(ChallengeEntry)
        .filter(ChallengeEntry.user_id == user_id, ChallengeEntry.challenge_id == challenge_id)
        .one_or_none()
    )


@router.post(
    "/challenges/{challenge_id}/entries",
    response_model=ChallengeEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def send_entry(
    challenge_id: ChallengeIdPath,
    payload: ChallengeEntryCreate,
    response: Response,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChallengeEntry:
    """Send the club an entry, or tell it the hiker finished. Once per challenge.

    **The replay is answered before any refusal.** An entry that committed
    and lost its response is resent by the outbox, possibly after the window
    has closed; it was accepted, so it is answered 200, not refused.

    Then, in this order, each a 409 whose `detail` the phone shows as it is:
    already sent (under another id), no club here takes entries for this
    challenge, and the window has closed. A finished notice skips the second
    refusal's `takes_entries` half: it is accepted whenever a claimed club
    owns the challenge and has published it, because telling a club you
    finished is not entering its drawing - but a draft takes nothing.

    **Judged by when it arrives, and that is a known gap.** The outbox queues
    entries, so one sent at camp on the closing evening and flushed in town
    two days later is refused here, although the hiker pressed send in time.
    The request carries no authored time to judge it by, and taking the
    phone's word for a drawing's deadline is a decision about the club's
    rules that nobody has made. `CLOSE_LEEWAY` covers the time zone, not the
    queue.
    """
    entry_id = str(payload.id)

    settled = _own_entry(db, entry_id, current_user, challenge_id)
    if settled is not None:
        response.status_code = status.HTTP_200_OK
        return settled

    if _entry_for(db, current_user.id, challenge_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ALREADY_SENT)

    owned = db.get(ClubChallenge, challenge_id)
    club = db.get(Club, owned.club_id) if owned is not None else None
    # A club that is not `claimed` - held, contested, deleted - collects
    # nobody's name and address, whatever its row says: `claimed` is the one
    # state in which somebody at the organization proved its domain.
    # And it is the org the hiker was shown, proved by its domain. Owning an id
    # is first come, and a slug is whatever a registrant typed, so neither
    # says the club is the ATC. The published list names its publisher's web
    # domain (publishers.json, reviewed by a maintainer), the phone sends it,
    # and a club holds the entry only if it proved that domain - which is
    # what `claimed` means. A stranger who registered the slug `atc` with a
    # domain of their own collects nothing.
    if (
        owned is None
        or club is None
        or club.state != OrgState.claimed
        or (club.domain or "").strip().lower() != payload.org_domain
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NOT_TAKING_ENTRIES)
    if not payload.finished_only and not owned.takes_entries:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NOT_TAKING_ENTRIES)
    # "A draft takes no entries" (features/CHALLENGES.md) covers the finished
    # notice too: it carries a name, and a club whose list is not published
    # yet has told no hiker it is collecting any.
    if payload.finished_only and (owned.definition or {}).get("status") != "published":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NOT_TAKING_ENTRIES)

    now = utc_now()
    if has_closed(owned.window_closes, now):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=closed_sentence(owned.window_closes))

    # How this server held each listed item as the entry arrived - see the
    # model for why it is kept rather than read again at download.
    held = {
        item_id: how
        for item_id, how in db.query(ChallengeTag.item_id, ChallengeTag.how).filter(
            ChallengeTag.user_id == current_user.id,
            ChallengeTag.challenge_id == challenge_id,
        )
    }
    item_ids = list(payload.item_ids)
    entry = ChallengeEntry(
        id=entry_id,
        user_id=current_user.id,
        challenge_id=challenge_id,
        club_id=owned.club_id,
        name=payload.name,
        email=payload.email,
        mailing_address=payload.mailing_address,
        item_ids=item_ids,
        hand_item_ids=[item for item in item_ids if held.get(item) == TagHow.hand],
        untagged_item_ids=[item for item in item_ids if item not in held],
        finished_only=payload.finished_only,
        consented_at=now,
        sent_at=now,
    )
    db.add(entry)
    try:
        return commit_and_refresh(db, entry)
    except IntegrityError:
        db.rollback()
        settled = _own_entry(db, entry_id, current_user, challenge_id)
        if settled is not None:
            response.status_code = status.HTTP_200_OK
            return settled
        if _entry_for(db, current_user.id, challenge_id) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ALREADY_SENT) from None
        raise


# ------------------------------------------------------------------ #
# The club's side
# ------------------------------------------------------------------ #


def _owned(db: Session, access: OrgAccess, challenge_id: str) -> ClubChallenge:
    """This club's saved challenge, or 404.

    404 for a challenge another club owns, not 403 - a 403 would confirm the
    id is somebody's (test_org_permission_matrix.py's cross-org rule).
    """
    row = db.get(ClubChallenge, challenge_id)
    if row is None or row.club_id != access.club.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This organization has no such challenge")
    return row


def _one_at_a_time(db: Session, key: str) -> None:
    """Serialise the count-then-insert below a cap, per account or per club.

    The caps count rows and then insert, and two requests between the two
    statements both pass: ten concurrent tags against a cap of two stored ten
    (second security review, 2026-10-01). A transaction-scoped advisory lock
    on Postgres - the engine CI and production run - holds the second until
    the first commits. Other engines have no such lock and are not where a
    concurrent client can reach.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})


def _refuse_unless_claimed(access: OrgAccess) -> None:
    """A claimed organization reads its entrants and its counts; a frozen one -
    two people contesting the same org - does not, whoever of them is an admin
    today. The save and the entry routes already stop at anything but
    `claimed`."""
    if access.club.state != OrgState.claimed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This organization's entries are held until somebody at it is confirmed again.",
        )


def _floored(count: int) -> int | None:
    """A count of distinct hikers, or None below the floor."""
    return count if count >= CHALLENGE_COUNT_FLOOR else None


def _hikers_in(db: Session, challenge_ids: list[str]) -> dict[str, int]:
    """Distinct hikers with at least one tag, per challenge."""
    if not challenge_ids:
        return {}
    rows = (
        db.query(ChallengeTag.challenge_id, func.count(func.distinct(ChallengeTag.user_id)))
        .filter(ChallengeTag.challenge_id.in_(challenge_ids))
        .group_by(ChallengeTag.challenge_id)
        .all()
    )
    return {challenge_id: int(count) for challenge_id, count in rows}


def _finished(db: Session, challenge_ids: list[str]) -> dict[str, int]:
    if not challenge_ids:
        return {}
    rows = (
        db.query(ChallengeEntry.challenge_id, func.count(ChallengeEntry.id))
        .filter(ChallengeEntry.challenge_id.in_(challenge_ids))
        .group_by(ChallengeEntry.challenge_id)
        .all()
    )
    return {challenge_id: int(count) for challenge_id, count in rows}


def _window(definition: dict[str, Any]) -> ChallengeWindowOut:
    window = definition.get("window") or {}
    return ChallengeWindowOut(opens=window.get("opens"), closes=window.get("closes"))


@router.get("/clubs/{slug}/challenges", response_model=list[ClubChallengeSummary])
def list_club_challenges(
    slug: str,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> list[ClubChallengeSummary]:
    """The console's Challenges list: each saved challenge and its counts.

    Admins only. Nothing here names a hiker, and `hikers_in` is withheld
    below the floor - but which challenges a club is drafting is the club's
    unpublished work, which is the registry's reason for the same gate.
    """
    # Counts too are the org's to read only while it is claimed - the CSV's
    # and the counts route's rule, which this list's `finished` and
    # `hikers_in` used to skip.
    _refuse_unless_claimed(access)
    rows = db.query(ClubChallenge).filter(ClubChallenge.club_id == access.club.id).order_by(ClubChallenge.challenge_id).all()
    ids = [row.challenge_id for row in rows]
    hikers = _hikers_in(db, ids)
    finished = _finished(db, ids)
    return [
        ClubChallengeSummary(
            challenge_id=row.challenge_id,
            name=str(row.definition.get("name", "")),
            status=str(row.definition.get("status", "")),
            window=_window(row.definition),
            takes_entries=row.takes_entries,
            pr_url=row.pr_url,
            updated_at=row.updated_at,
            definition=row.definition,
            hikers_in=_floored(hikers.get(row.challenge_id, 0)),
            finished=finished.get(row.challenge_id, 0),
        )
        for row in rows
    ]


@router.get("/clubs/{slug}/challenges/{challenge_id}/counts", response_model=ChallengeCountsOut)
def read_challenge_counts(
    slug: str,
    challenge_id: ChallengeIdPath,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> ChallengeCountsOut:
    """How many are walking it and how many finished - counts, never names."""
    _owned(db, access, challenge_id)
    _refuse_unless_claimed(access)
    hikers = _hikers_in(db, [challenge_id]).get(challenge_id, 0)
    return ChallengeCountsOut(
        hikers_in=_floored(hikers),
        finished=_finished(db, [challenge_id]).get(challenge_id, 0),
    )


@router.get(
    "/clubs/{slug}/challenges/{challenge_id}/entries",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "The finishers, one row per entry."}},
)
def download_entries(
    slug: str,
    challenge_id: ChallengeIdPath,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> Response:
    """The finishers, as a CSV the club opens in a spreadsheet. Admins only.

    **The one place a club reads a hiker's name**, and only the name, address
    and list a hiker typed into an entry and sent to this club. Admin rather
    than supervisor, `/clubs/{slug}/export`'s line: a supervisor running a
    crew has no need of a drawing's entrants' home addresses.

    Every text cell goes through `spreadsheet_safe`, because every one of them
    was typed by somebody other than the person opening the file.

    The file starts with a UTF-8 byte-order mark. Excel reads a CSV without
    one in the machine's legacy code page, which turns "Zoë" into "ZoÃ«" in
    front of the club; Google Sheets and every CSV parser that reads
    `utf-8-sig` ignore it.
    """
    _owned(db, access, challenge_id)
    _refuse_unless_claimed(access)
    # This club's entries for the id - not every entry ever filed under it,
    # which an id that changed hands would otherwise pass along.
    entries = (
        db.query(ChallengeEntry)
        .filter(ChallengeEntry.challenge_id == challenge_id, ChallengeEntry.club_id == access.club.id)
        .order_by(ChallengeEntry.sent_at, ChallengeEntry.id)
        .all()
    )

    buffer = io.StringIO()
    # Every cell quoted: an Excel set to a `;` separator splits an unquoted
    # `Jo;=1+1` into a second cell that starts with `=`, past the guard.
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(CSV_COLUMNS)
    for entry in entries:
        item_ids = [str(item) for item in (entry.item_ids or [])]
        cells = (
            # Naive UTC stored, so the `Z` is put back on - account_export.py's
            # reason: an unmarked UTC time in a file is read as local.
            entry.sent_at.isoformat() + "Z",
            entry.name,
            entry.email or "",
            entry.mailing_address or "",
            str(len(item_ids)),
            ";".join(item_ids),
            # As the server held them when the entry arrived (the model's note).
            ";".join(str(item) for item in (entry.hand_item_ids or [])),
            ";".join(str(item) for item in (entry.untagged_item_ids or [])),
            "true" if entry.finished_only else "false",
        )
        writer.writerow([spreadsheet_safe(cell) for cell in cells])

    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        # The id is ID_PATTERN-checked in the path and in the row, so it can
        # neither close the quoted filename nor start a second header.
        headers={"Content-Disposition": f'attachment; filename="{challenge_id}-entries.csv"'},
    )


def _depth(value: Any, level: int = 0) -> int:
    """How deeply `value` nests, stopping early past the cap."""
    if level > DEFINITION_MAX_DEPTH:
        return level
    if isinstance(value, dict):
        return max((_depth(child, level + 1) for child in value.values()), default=level + 1)
    if isinstance(value, list):
        return max((_depth(child, level + 1) for child in value), default=level + 1)
    return level


def _checked_definition(
    challenge_id: str, definition: dict[str, Any], slug: str, domain: str | None = None
) -> tuple[date | None, str, bool]:
    """(window closes, status, has a reward), or a 422 naming what is wrong.

    **Only as far as this backend reads it.** The id, the org and the name
    say what the row is; the status, the window and the reward decide whether
    the row may take entries and until when. Everything else - that the
    places exist, lie on the club's own trails, and within their radius -
    is `pipeline/lib/challenges.py`'s job when the reviewed file lands, and a
    second, partial copy of those checks here would disagree with it the
    first time either changed.
    """

    def refuse(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

    try:
        # allow_nan=False: a NaN or Infinity is not JSON, and Postgres refused
        # it at commit with a 500 on the admin's own save.
        size = len(json.dumps(definition, allow_nan=False))
    except ValueError:
        raise refuse("definition holds a number that is not a number (NaN or Infinity).") from None
    if size > DEFINITION_MAX_CHARS:
        raise refuse(f"definition is larger than {DEFINITION_MAX_CHARS:,} characters.")
    if _depth(definition) > DEFINITION_MAX_DEPTH:
        # A definition nested hundreds deep saved fine and then failed every
        # list read with a 500 - one admin breaking the club's whole console.
        raise refuse(f"definition is nested deeper than {DEFINITION_MAX_DEPTH} levels.")
    if definition.get("id") != challenge_id:
        raise refuse(f"definition.id must be {challenge_id!r}, the challenge id in the address.")
    # The org is the club saving it, or a publisher whose domain the club
    # proved (app/core/trail_challenge.py's PUBLISHER_DOMAINS), and the id
    # starts with that org - the rules the console already follows
    # (org/screens/Challenges.tsx's newChallengeId) and the pipeline holds for
    # the org, which must be the directory its reviewed file sits in. They
    # stop a club saving another org's id first and locking that org out of
    # its own challenge. Not airtight between ordinary slugs - `ramapo` can
    # still save `ramapo-trail-conference-…` - which is why the entry route
    # also checks the domain the hiker was shown.
    org = definition.get("org")
    if not isinstance(org, str) or not may_publish_as(org, slug=slug, domain=domain):
        raise refuse(f"definition.org must be {slug!r}, the organization saving it.")
    if not challenge_id.startswith(f"{org}-"):
        raise refuse(f"A challenge id starts with the organization's slug: {org}-…")
    name = definition.get("name")
    if not isinstance(name, str) or not name.strip():
        raise refuse("definition.name must not be empty.")
    if not isinstance(definition.get("items"), list):
        raise refuse("definition.items must be a list.")
    challenge_status = definition.get("status")
    if challenge_status not in DEFINITION_STATUSES:
        raise refuse(f"definition.status must be one of {', '.join(DEFINITION_STATUSES)}.")

    window = definition.get("window")
    if window is not None and not isinstance(window, dict):
        raise refuse("definition.window must be an object with opens and closes.")
    dates: dict[str, date | None] = {}
    for end in ("opens", "closes"):
        raw = (window or {}).get(end)
        try:
            dates[end] = date.fromisoformat(raw) if raw is not None else None
        except (TypeError, ValueError):
            raise refuse(f"definition.window.{end} must be a YYYY-MM-DD date or null.") from None

    return dates["closes"], challenge_status, definition.get("reward") is not None


@router.put("/clubs/{slug}/challenges/{challenge_id}", response_model=ClubChallengeOut)
def save_club_challenge(
    slug: str,
    challenge_id: ChallengeIdPath,
    payload: ClubChallengeUpsert,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> ClubChallenge:
    """Save a challenge's definition, making it this club's. Admins only.

    **Saving publishes nothing.** Hikers see what the pipeline builds from a
    reviewed file a maintainer merged - `/publish` below is how a saved
    definition becomes a pull request, and a person merges it or does not.
    What saving does do is claim the id: entries for it go to this club.

    **Only a claimed organization saves one**, `open_registry_pr`'s rule: a
    held registration is a stranger who typed a domain, and owning a
    challenge id is what routes hikers' names and addresses somewhere.

    **`takes_entries` is refused while the definition is a draft or offers
    no reward.** "A draft takes no entries" is the maintainer's decision of
    2026-09-30 (features/CHALLENGES.md), and with no reward there is nothing
    to enter - the no-reward finish is a finished notice, which needs no
    switch. Refused rather than quietly switched off, so a club moving a
    challenge back to draft is told its entries stop.
    """
    club = access.club
    if club.state != OrgState.claimed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Only a claimed organization can save a challenge. Somebody at the organization has to confirm it first."),
        )

    closes, challenge_status, has_reward = _checked_definition(challenge_id, payload.definition, club.slug, club.domain)

    row = db.get(ClubChallenge, challenge_id)
    taken = "Another organization already has a challenge with this id. Pick another."
    if row is not None and row.club_id != club.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=taken)
    if row is None:
        _one_at_a_time(db, f"club-challenges:{club.id}")
    if (
        row is None
        and db.query(func.count(ClubChallenge.challenge_id)).filter(ClubChallenge.club_id == club.id).scalar()
        >= CHALLENGES_PER_CLUB_CAP
    ):
        # Each saved id can become a branch and a pull request in this
        # repository (`/publish`); the cap is what bounds them.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An organization can keep {CHALLENGES_PER_CLUB_CAP} challenges. "
                "Ask OurHike to remove one you no longer need before saving another."
            ),
        )

    takes_entries = payload.takes_entries if payload.takes_entries is not None else (row.takes_entries if row else False)
    if takes_entries and (challenge_status != "published" or not has_reward):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "A challenge takes entries only once it is published and offers a reward. "
                "Turn entries off to save it as a draft or without a reward."
            ),
        )

    if row is None:
        row = ClubChallenge(challenge_id=challenge_id, club_id=club.id)
        db.add(row)
    row.definition = payload.definition
    row.window_closes = closes
    row.takes_entries = takes_entries
    row.updated_at = utc_now()
    row.updated_by = access.person_id
    try:
        return commit_and_refresh(db, row)
    except IntegrityError:
        # Two saves of a new id at once: the loser is told, rather than 500.
        db.rollback()
        winner = db.get(ClubChallenge, challenge_id)
        if winner is not None and winner.club_id != club.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=taken) from None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somebody saved this challenge at the same moment. Load it again and save.",
        ) from None


@router.post("/clubs/{slug}/challenges/{challenge_id}/publish", response_model=ChallengePublishOut)
def publish_club_challenge(
    slug: str,
    challenge_id: ChallengeIdPath,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> ChallengePublishOut:
    """Put the saved definition up for review as a pull request.

    Writes one file, `pipeline/reference/challenges/<slug>/<id>.json`, through
    the registry's own opener (core/registry_pr.py) behind the same switch -
    off unless `registry_pr_enabled` and a token are both set - and it never
    merges. A refusal is answered 200 with `pull_request: null` and a
    sentence, because the save it follows already succeeded and nothing about
    it is undone; the reason GitHub gave is not passed on, since it can name
    the repository or why a token was refused.
    """
    row = _owned(db, access, challenge_id)

    if not settings.registry_pr_enabled or not settings.registry_pr_token:
        return ChallengePublishOut(
            pull_request=None,
            detail=(
                "Saved, and not sent for review: this deployment does not open pull requests yet. "
                "Nothing reaches a phone until a maintainer merges the challenge's file."
            ),
        )

    try:
        opened = open_challenge_pr(access.club, challenge_id, row.definition)
    except RegistryPrRefused:
        return ChallengePublishOut(
            pull_request=None,
            detail=(
                "The pull request could not be opened just now. Your saved challenge is unchanged, "
                "and publishing again will try it."
            ),
        )

    row.pr_url = opened.url
    db.commit()
    return ChallengePublishOut(
        pull_request=opened.url,
        detail=(
            "Your challenge is now a pull request against the public repository. A maintainer reviews "
            "and merges it, and the next data refresh is what reaches a phone - open is not published."
        ),
    )
