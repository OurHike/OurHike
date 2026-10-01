"""The three challenge tables (#1780, features/CHALLENGES.md "On the server").

Named `trail_challenge` at the module level because `challenge` already means
proof-of-work here (`core/challenge.py`, `ChallengeSpend` in nomination.py).

**What reaches this server is deliberately small** - design principle 6, "the
hiker's record is theirs": a tag is an item id, a time and how it was made,
and nothing about where the hiker was. No GPS track, no photo, no register
line. An entry is what the hiker typed into the entry form and pressed send
on, and nothing else.

**`challenge_id` and `item_id` are soft strings, not foreign keys.** A
challenge's definition is a reviewed file the pipeline publishes
(`pipeline/reference/challenges/<org>/<id>.json`), exactly as a workday is
(`volunteer_hours.work_project_id`'s precedent). A tag is accepted whether or
not any club has saved that challenge here: the ATC's list is published as a
draft from the reviewed file alone, and a hiker tagging a place on it must not
lose the tag because no console ever touched it.

`club_challenges` is the one place a challenge id is tied to a club, and it
is what the entry and console routes gate on. See app/models/profile.py for
the naive-UTC timestamp convention every DateTime here follows.
"""

import enum

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint

from app.core.time import utc_now
from app.db.base import Base


class TagHow(str, enum.Enum):
    """How a tag was made - features/CHALLENGES.md's second qualification.

    `gps`: the day's track passed within the item's radius and the hiker
    confirmed it on Today. `hand`: the hiker tagged it from the place card or
    the challenge page, because GPS has gaps. Both are recorded, and an entry
    carries the difference to the club, so the club decides what a hand tag is
    worth rather than the app deciding for it.
    """

    gps = "gps"
    hand = "hand"


class ChallengeTag(Base):
    """One place a hiker tagged on one challenge.

    Unique on (hiker, challenge, item): a place is tagged or it is not, and a
    second tag of it - the same hiker on a second device - is the same fact
    arriving twice, answered with the row already here (routers/
    trail_challenges.py).
    """

    __tablename__ = "challenge_tags"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", "item_id", name="uq_challenge_tags_user_challenge_item"),)

    # The client's outbox idempotency key, a UUID it minted when the tag was
    # made - report.py's id, for report.py's reason: tags are made at camp,
    # and camp has no signal.
    id = Column(String, primary_key=True)

    user_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
    challenge_id = Column(String(120), nullable=False)
    item_id = Column(String(120), nullable=False)
    how = Column(Enum(TagHow, native_enum=False, length=10), nullable=False)

    # When the hiker tagged it, on the phone's clock - the time a tag after
    # the window closes is judged by. `received_at` is server truth, and the
    # two differ by however long the outbox waited for signal.
    authored_at = Column(DateTime, nullable=False)
    received_at = Column(DateTime, nullable=False, default=utc_now)


class ChallengeEntry(Base):
    """What a hiker sent a club at the finish: an entry, or a finished notice.

    One per hiker per challenge. The name, the address and the list are the
    hiker's own words about themselves, sent to one club on purpose - this is
    the only row in the feature that names anybody, and the club reads it
    only as the finishers' CSV.
    """

    __tablename__ = "challenge_entries"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", name="uq_challenge_entries_user_challenge"),)

    # The client's outbox idempotency key, as on `challenge_tags`.
    id = Column(String, primary_key=True)

    user_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)
    challenge_id = Column(String(120), nullable=False)

    name = Column(String(200), nullable=False)
    # At least one of the two for an entry; neither for a finished notice
    # (schemas/trail_challenge.py). 320 is RFC 5321's ceiling, schemas/
    # common.py's EMAIL_MAX_CHARS.
    email = Column(String(320), nullable=True)
    mailing_address = Column(Text, nullable=True)

    # The item ids the hiker says they tagged, as sent. Not checked against
    # `challenge_tags`: a tag can still be queued on the phone when the entry
    # arrives, and the club, not this server, decides what counts. The CSV
    # says which of them were tagged by hand.
    item_ids = Column(JSON, nullable=False)

    # The no-reward finish screen's "Let the club know you finished": a name
    # and the day, and never contact details or a list. Accepted whenever the
    # club owns the challenge, whether or not it takes entries.
    finished_only = Column(Boolean, nullable=False, default=False)

    # When the hiker's consent reached this server. The form refuses to send
    # without it, so this is the moment the consented request arrived rather
    # than a time the phone claims - which is the one a club answering "when
    # did this person agree" can stand behind.
    consented_at = Column(DateTime, nullable=False)
    # Server receive time, and the finish date a finished notice carries.
    sent_at = Column(DateTime, nullable=False, default=utc_now)


class ClubChallenge(Base):
    """A club's saved challenge definition, and the link that makes it theirs.

    `definition` is the reviewed file's shape (features/CHALLENGES.md "The
    reviewed file") as the console last saved it. It is NOT what hikers see:
    that is the pipeline's published artifact, built from the reviewed file a
    maintainer merged. This row is the draft on the console's desk and the
    ownership record the entry routes read.

    `window_closes` is copied out of the definition so the entry route can
    refuse without parsing JSON. `takes_entries` is not in the definition at
    all: it is the club's own switch, set from the console.
    """

    __tablename__ = "club_challenges"

    challenge_id = Column(String(120), primary_key=True)
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)

    definition = Column(JSON, nullable=False)
    # definition.window.closes, parsed. Null means the challenge never closes.
    window_closes = Column(Date, nullable=True)

    # Whether this club takes entries through OurHike at all. Off until an
    # admin turns it on, and refused while the definition is a draft or has
    # no reward (routers/trail_challenges.py): "a draft takes no entries" is
    # the maintainer's decision of 2026-09-30, and with no reward there is
    # nothing to enter.
    takes_entries = Column(Boolean, nullable=False, default=False)

    # The pull request this definition was last put up in, when the opener is
    # switched on. Null on every deployment where it is not.
    pr_url = Column(String, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=utc_now)
    updated_by = Column(String, ForeignKey("profiles.id"), nullable=True)
