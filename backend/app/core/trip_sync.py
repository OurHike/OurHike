"""What happens when two devices have both edited the same trip (#892).

features/ACCOUNT_SYNC.md's rule, and the issue calls it non-negotiable:
**a conflict keeps both.** The newer keeps its name, the older is kept
beside it named for where it came from, and the hiker opens both, sees the
difference and deletes one.

That is one moment of friction bought in exchange for never being the app
that silently ate a fortnight of planning. `client/src/lib/trips.ts` already
refuses to delete the legacy `ourhike:plan` key on exactly this trade -
"leaving ~24 KB in place costs nothing against irreversibly destroying the
only copy of somebody's plan if this code is wrong."

WHY THE RULE IS THE SERVER'S AND NOT EACH DEVICE'S

The server is the only party that can see both versions. A device knows what
it did and what it last heard; it cannot know that a laptop in another time
zone edited the same trip an hour ago. Putting the rule here also means every
device converges on the same answer without each of them implementing it -
and a device that implemented it slightly differently would produce a
divergence that looks exactly like the data loss this rule exists to prevent.

HOW A CONFLICT IS DETECTED, AND WHY IT IS NOT A TIMESTAMP COMPARISON

Each uploaded trip carries `base_updated_at`: the server stamp this device
last saw for that trip. If the row still carries that stamp, nothing has
happened since this device last looked, and the upload is an ordinary edit.
If it carries a different one, somebody else wrote in between - which is the
definition of the conflict, established without comparing any clock to any
other clock. `lib/preferencesSync.ts` reaches the same conclusion for phase
A's simpler payload, and for the same reason: a device's clock is not
evidence about a server's.

`base_updated_at` of None means "this device believes this trip is new". If
a row already exists under that id, that too is a conflict - two devices
minted the same id, or more likely one device is re-uploading a trip it
created before a sync it has since forgotten.

THE CASE THE DOC DOES NOT SPECIFY: DELETE AGAINST EDIT

The doc spells out edit-against-edit. Delete-against-edit is left open, and
the answer taken here is that **the tombstone lands and the other device's
edit is kept beside it as a copy**. Both acts were the hiker's, and neither
is knowable as the intended one - so this resolves toward the rule that is
non-negotiable rather than toward the one that is convenient. A resurrected
copy is visible in the list and can be deleted again in one tap; an edit
destroyed by somebody else's delete is invisible and gone.

It is genuinely annoying, and it is called out here rather than discovered:
a hiker who deletes a trip on their laptop while their phone had unsent
edits will see something come back, once, named as a copy.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UploadedTrip:
    """One trip as a device is offering it."""

    id: str
    #: The trip as the client holds it, or None when this upload is the
    #: hiker's own delete.
    document: dict | None
    #: The server stamp this device last saw for this trip; None when the
    #: device believes it is new. See the module docstring.
    base_updated_at: datetime | None
    #: True when this upload is a deletion rather than an edit.
    deleted: bool = False


@dataclass(frozen=True)
class StoredTrip:
    """The row as it stands, reduced to what the rule reads."""

    id: str
    document: dict | None
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True)
class TripWrite:
    """One row the caller should write. The rule decides; the router does."""

    id: str
    document: dict | None
    deleted: bool
    #: True when this write is the kept-beside copy rather than the trip the
    #: device was talking about. Carried so a caller can count them, and so a
    #: test can tell a copy from an overwrite rather than inferring it.
    is_conflict_copy: bool = False


#: How a kept-beside copy is named.
#:
#: The doc's example is *"Grayson Highlands (from the phone, 12 Aug)"*, and
#: **the client has no device name to put there** - nothing in
#: `client/src/lib/` records what kind of device it is running on, and
#: inventing one from a user agent would be a guess printed as a fact. So the
#: copy says what is actually known: another device edited this, on this date.
#:
#: The date is ISO rather than "12 Aug" because this is a server minting a
#: name that becomes the trip's real name from then on, and a server has no
#: business choosing a locale's month abbreviation. A hiker can rename it.
CONFLICT_SUFFIX = "(edited on another device, {date})"


def name_for_copy(document: dict | None, at: datetime) -> str:
    """What the kept-beside copy is called."""
    name = (document or {}).get("name") or "Untitled trip"
    return f"{name} {CONFLICT_SUFFIX.format(date=at.date().isoformat())}"


def document_for_copy(document: dict | None, at: datetime, copy_id: str) -> dict:
    """The kept-beside copy's document: renamed, and RE-IDENTIFIED (#1036).

    The re-id is the load-bearing half and it was missing. A document carries
    its own ``id``, and the client stores that rather than the row id it
    arrived under (``tripsSync.tripFrom``), so a copy built as
    ``{**document, "name": ...}`` landed in the device's store under the very
    id it was created to sit beside. Edit-vs-edit produced two records sharing
    one id, and a later delete of that id took both; delete-vs-edit lost the
    copy outright whenever the client applied the tombstone last, which
    nothing in the exchange orders.

    So the copy's document id is the copy's row id - the same value, minted
    once - and the two branches below pass it in rather than each rebuilding
    the dict. The original keeps its id, which is what leaves ``openId`` and
    any group membership pointing at the record that survives.
    """
    return {**(document or {}), "id": copy_id, "name": name_for_copy(document, at)}


def resolve_upload(
    uploaded: UploadedTrip,
    stored: StoredTrip | None,
    now: datetime,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> list[TripWrite]:
    """What to write for one uploaded trip. Never more than two rows.

    Returns an empty list when there is nothing to do, one write for the
    ordinary case, and two when the rule keeps both - the second being the
    copy.
    """
    if stored is None:
        # Nothing here yet. A delete of a trip the server never saw is not an
        # error and not a no-op: the tombstone is what stops ANOTHER device
        # that does have the trip from re-uploading it for ever.
        return [TripWrite(id=uploaded.id, document=uploaded.document, deleted=uploaded.deleted)]

    unchanged_since_this_device_looked = uploaded.base_updated_at is not None and uploaded.base_updated_at == stored.updated_at
    if unchanged_since_this_device_looked:
        return [TripWrite(id=uploaded.id, document=uploaded.document, deleted=uploaded.deleted)]

    # A trip already tombstoned here, deleted again by a device that had not
    # heard: the same act twice, not a conflict. Writing a copy would
    # resurrect what the hiker deleted on both devices.
    if stored.deleted_at is not None and uploaded.deleted:
        return []

    # An UNCHANGED re-upload of what the server already holds is somebody
    # syncing twice, not two people disagreeing. Compared by content rather
    # than by stamp, because the stamp is exactly what is out of date here.
    if not uploaded.deleted and stored.document == uploaded.document:
        return []

    # The conflict. Both survive: the stored row is left exactly as it is,
    # and what this device is holding is written beside it under a new id.
    #
    # The deleted case lands here too, and the delete is applied to the
    # original id while the SERVER's document is the one kept beside it -
    # see the module docstring on why the copy is the survivor rather than
    # the casualty.
    if uploaded.deleted:
        copy_id = new_id()
        return [
            TripWrite(id=uploaded.id, document=None, deleted=True),
            TripWrite(
                id=copy_id,
                document=document_for_copy(stored.document, now, copy_id),
                deleted=False,
                is_conflict_copy=True,
            ),
        ]

    copy_id = new_id()
    return [
        TripWrite(
            id=copy_id,
            document=document_for_copy(uploaded.document, now, copy_id),
            deleted=False,
            is_conflict_copy=True,
        )
    ]
