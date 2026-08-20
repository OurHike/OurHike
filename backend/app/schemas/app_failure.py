"""The wire shape of an app-failure report (#848).

**One rule governs this whole file: this endpoint does not refuse reports.**

That is a stronger commitment than the rest of the API makes, and it is not
a relaxation of standards - it follows from what the client does with a
refusal. `client/src/lib/api.ts`'s `permanentFailureReason` marks any 422
that does not name `authored_at` as permanent, and `flushOutbox` then stops
retrying that item and shows the hiker "this version of the app is too old".
A 422 here is therefore not "send it again properly"; it is the report never
arriving, for a class of report whose entire purpose is that somebody hears
about it.

So every constraint below is applied by TRUNCATING OR DROPPING rather than
by raising:

  - Over-long text is cut to its cap, not rejected. A hiker who wrote two
    thousand words about nearly walking off a ledge should lose the tail,
    not the report.
  - A `harms` entry this server does not recognise is dropped, and the rest
    of the list is kept. An older server meeting a newer client's fifth harm
    should keep the four it understands.
  - A future-dated `authored_at` is accepted as sent, unlike
    `ReportCreate`'s, which refuses one. That refusal is right for a
    condition report - a maintainer reading a queue by time is misled by a
    backdated blowdown - and wrong here: nothing sorts this table by a
    hiker's claim, `received_at` is the server's own truth beside it, and the
    cost of being strict is losing the report over a phone clock.

The caps themselves are @unvalidated - picked, not measured. 8,000
characters for `what_happened` is twice `NoteText`'s (schemas/common.py),
on the reasoning that this is somebody describing an incident rather than
labelling a blowdown, and 500 for the two short fields is a generous line.
What would settle them is real reports from real hikers; until then the
numbers are round because nobody has anything better, and they are enforced
by truncation so being wrong about them costs a tail rather than a report.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator

from app.core.time import UtcDatetime
from app.models.app_failure import Harm

# See the module docstring: picked, enforced by truncation, @unvalidated.
WHAT_HAPPENED_MAX_CHARS = 8000
SHORT_FIELD_MAX_CHARS = 500

# A body this size is not a hiker. The list is capped before the unknown
# values are dropped, so a client sending ten thousand junk entries cannot
# spend server time having each one looked up.
HARMS_MAX_ENTRIES = 16


def _clipped(limit: int):
    """A validator that cuts a string to `limit` instead of refusing it."""

    def clip(value: Any) -> Any:
        if isinstance(value, str) and len(value) > limit:
            return value[:limit]
        return value

    return clip


def _known_harms(value: Any) -> Any:
    """The recognised harms in `value`, in order, without duplicates.

    Anything else is dropped rather than raised on - see the module
    docstring. A non-list is passed through untouched so pydantic produces
    its ordinary type error for, say, a bare string; that is a malformed
    request rather than a client this server is merely older than.
    """
    if not isinstance(value, list):
        return value

    known = {harm.value for harm in Harm}
    kept: list[str] = []
    for entry in value[:HARMS_MAX_ENTRIES]:
        if isinstance(entry, str) and entry in known and entry not in kept:
            kept.append(entry)
    return kept


WhatHappened = Annotated[str, BeforeValidator(_clipped(WHAT_HAPPENED_MAX_CHARS))]
ShortText = Annotated[str, BeforeValidator(_clipped(SHORT_FIELD_MAX_CHARS))]
KnownHarms = Annotated[list[Harm], BeforeValidator(_known_harms)]


class AppFailureCreate(BaseModel):
    """What the client sends.

    No `reporter_id`, no `received_at`, no `answered_at` - all server-owned,
    and silently ignored if a client sends them (pydantic's default).
    """

    # The idempotency key, and a typed UUID for the same security reason
    # `ReportCreate.id` is one: it becomes the primary key. Optional, falling
    # back to a server-minted one, so a caller that omits it is not a 422 -
    # which on this endpoint would mean a lost report.
    id: uuid.UUID | None = None

    what_happened: WhatHappened

    whereabouts: ShortText | None = None

    # The contact detail this whole path exists to carry. Unparsed and
    # unvalidated on purpose - see the column comment in
    # app/models/app_failure.py.
    contact: ShortText | None = None

    harms: KnownHarms = []

    build: ShortText | None = None
    was_offline: bool | None = None

    # Accepted as sent, future dates included. See the module docstring.
    authored_at: datetime | None = None


class AppFailureAck(BaseModel):
    """What comes back: that it landed, and nothing else.

    Deliberately not the stored row. There is nothing here the sender does
    not already have, and a response that echoed `contact` back would be
    this table's first opportunity to serve a contact detail to a caller -
    the thing app/models/app_failure.py's docstring exists to keep
    unavailable.
    """

    id: str
    received_at: UtcDatetime
