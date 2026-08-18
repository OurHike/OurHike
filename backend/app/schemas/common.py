"""Shared field types for wire-level inputs (#658).

FiniteFloat exists because the claim that scoped the one NaN validator this
codebase had ("JSON cannot deliver them - FastAPI's parser refuses the bare
NaN token", the old schemas/report.py comment) is empirically false on the
pinned stack: Python's json module both emits and accepts the bare `NaN`
token, so a client - or anything speaking JSON loosely - can deliver NaN and
Infinity into any float field. What a NaN does downstream is never a loud
error: every comparison against it is False, so a NaN mile is silently
absent from every banner, a NaN hike reference makes derive_direction
return SOBO unconditionally, and a NaN start_mile_marker survives
moderation and serializes as `null` in a required public field with no API
repair path. One shared type closes the class at the wire.

NoteText is the byte-cap the photo path got (#379) and the text paths did
not. The compounding failure it closes: an unbounded note on an unpaginated
public list means one valid 50 MB note, once verified, ships to every
anonymous GET caller on every sync. 4,000 characters is picked, not
measured - roughly a page of text, an order of magnitude above the longest
legitimate note observed in test data - and is @unvalidated: real reports
from real hikers would settle where the ceiling belongs.
"""

from typing import Annotated

from pydantic import Field

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]

NOTE_MAX_CHARS = 4000
NoteText = Annotated[str, Field(max_length=NOTE_MAX_CHARS)]
