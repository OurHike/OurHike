"""What a card and a pin may say about a place the field disputes (#876).

One shape, and it is deliberately small: this is a VERDICT, not the evidence
behind it. The evidence is the notes, which are already public in the
hiker's own words - what cannot travel is `reporter_id`, and corroboration
is exactly the computation that needs it (features/FIELD_NOTES.md §6, #252).
So `core/disputes.py` reads the identities and this is what leaves.
"""

from pydantic import BaseModel

from app.core.time import UtcDatetime


class DisputeOut(BaseModel):
    """One place, reported missing."""

    poi_id: str

    #: How many distinct accounts said so inside the decay window. The card
    #: prints it ("2 hikers reported this missing"), so it counts ACCOUNTS
    #: rather than notes - two notes from one person is one observation.
    accounts: int

    #: The most recent disputing observation, for the card's "most recently
    #: 4 days ago". Never null on a served row: a dispute with no date could
    #: not have passed the decay check that got it here.
    latest_at: UtcDatetime

    #: True when a maintainer whose assignment covers that mile is among the
    #: disputers. The card says so, because "the person who looks after this
    #: stretch says it is gone" is a different sentence from "two hikers did".
    maintainer_said: bool
