"""Challenges - a club's list of places, a hiker's tags, and the finish (#1780).

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

**Nothing here refuses a tag.** A tag after the window closes is accepted and
flagged `late`; a tag for a challenge no club has saved is accepted and never
late. The phone's record is the hiker's, and a server that dropped a tag
because the console had not caught up would be deciding what the hiker did.
An ENTRY after close is refused, with a sentence the phone shows as it is.

**THE ONE THING THIS CANNOT CHECK, stated rather than implied.** Which club
owns a challenge id is first-come: the first claimed organization to save it
here. The published artifact says which organization a challenge belongs to,
and this backend does not read the published artifact - so a claimed club
that saved another club's challenge id first would receive that challenge's
entries. `claimed` is the guard that exists (a domain an admin proved), and
the maintainer's review of the reviewed file is the other; neither is the
backend knowing the publisher.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import func
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
    closed_from,
    closed_sentence,
    has_closed,
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
    "finished_only",
)


# ------------------------------------------------------------------ #
# A hiker's tags
# ------------------------------------------------------------------ #


def _late(db: Session, tag: ChallengeTag) -> bool:
    owned = db.get(ClubChallenge, tag.challenge_id)
    return owned is not None and has_closed(owned.window_closes, tag.authored_at)


def _tag_out(db: Session, tag: ChallengeTag) -> ChallengeTagOut:
    return ChallengeTagOut(
        id=tag.id,
        challenge_id=tag.challenge_id,
        item_id=tag.item_id,
        how=tag.how,
        authored_at=tag.authored_at,
        received_at=tag.received_at,
        late=_late(db, tag),
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
    """Record that the hiker tagged one item. Always accepted.

    **Idempotent twice over.** On `id`, for the outbox: a flush that committed
    and lost its response resends the same id and gets the same row with 200.
    And on the place itself: the same item tagged again under a NEW id is the
    same hiker on a second device, which is the same fact arriving twice, not
    an error - the row already here comes back with 200, and the first tag to
    arrive stands, including how it was made.
    """
    tag_id = str(payload.id)

    settled = _own_tag(db, tag_id, current_user, payload) or _same_place(
        db, current_user.id, payload.challenge_id, payload.item_id
    )
    if settled is not None:
        response.status_code = status.HTTP_200_OK
        return _tag_out(db, settled)

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
    refusal's `takes_entries` half and nothing else: it is accepted whenever
    a claimed club owns the challenge, because telling a club you finished is
    not entering its drawing.

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
    if owned is None or club is None or club.state != OrgState.claimed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NOT_TAKING_ENTRIES)
    if not payload.finished_only and not owned.takes_entries:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NOT_TAKING_ENTRIES)

    now = utc_now()
    if has_closed(owned.window_closes, now):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=closed_sentence(owned.window_closes))

    entry = ChallengeEntry(
        id=entry_id,
        user_id=current_user.id,
        challenge_id=challenge_id,
        name=payload.name,
        email=payload.email,
        mailing_address=payload.mailing_address,
        item_ids=list(payload.item_ids),
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
    """How many are walking it, how many tagged after it closed, how many finished.

    **The floor is on PEOPLE, for both withheld numbers.** `tags_after_close`
    counts tags, and one hiker can make thirty - so a tag count of thirty can
    describe one person. It is shown only when at least the floor's number of
    distinct hikers made late tags, which is the floor's actual promise
    ("a count of three is a description of three people", EVENTING.md §6).
    """
    row = _owned(db, access, challenge_id)
    hikers = _hikers_in(db, [challenge_id]).get(challenge_id, 0)

    late_tags = late_hikers = 0
    if row.window_closes is not None:
        late_tags, late_hikers = (
            db.query(func.count(ChallengeTag.id), func.count(func.distinct(ChallengeTag.user_id)))
            .filter(
                ChallengeTag.challenge_id == challenge_id,
                ChallengeTag.authored_at >= closed_from(row.window_closes),
            )
            .one()
        )

    return ChallengeCountsOut(
        hikers_in=_floored(hikers),
        tags_after_close=int(late_tags) if late_hikers >= CHALLENGE_COUNT_FLOOR else None,
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
    entries = (
        db.query(ChallengeEntry)
        .filter(ChallengeEntry.challenge_id == challenge_id)
        .order_by(ChallengeEntry.sent_at, ChallengeEntry.id)
        .all()
    )
    hand_tagged: set[tuple[str, str]] = set()
    if entries:
        hand_tagged = {
            (user_id, item_id)
            for user_id, item_id in db.query(ChallengeTag.user_id, ChallengeTag.item_id).filter(
                ChallengeTag.challenge_id == challenge_id,
                ChallengeTag.how == TagHow.hand,
                ChallengeTag.user_id.in_({entry.user_id for entry in entries}),
            )
        }

    buffer = io.StringIO()
    writer = csv.writer(buffer)
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
            ";".join(item for item in item_ids if (entry.user_id, item) in hand_tagged),
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


def _checked_definition(challenge_id: str, definition: dict[str, Any]) -> tuple[date | None, str, bool]:
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

    if definition.get("id") != challenge_id:
        raise refuse(f"definition.id must be {challenge_id!r}, the challenge id in the address.")
    org = definition.get("org")
    if not isinstance(org, str) or not org.strip():
        raise refuse("definition.org must name the organization publishing the challenge.")
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

    closes, challenge_status, has_reward = _checked_definition(challenge_id, payload.definition)

    row = db.get(ClubChallenge, challenge_id)
    taken = "Another organization already has a challenge with this id. Pick another."
    if row is not None and row.club_id != club.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=taken)

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
