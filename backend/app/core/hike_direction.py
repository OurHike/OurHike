"""Pure derivation of a Hike's direction of travel from its mile-marker
references.

See ../../../features/HIKER_SAFETY.md section 5 (the wrong-way/off-trail
alert): "[direction] needs to know *intended* direction, which SEGMENTS.md's
`Hike` already models (its overall start/end reference implies NOBO vs.
SOBO) - no new state needed, just reading what Segments already has." This
is that read: a small, dependency-free function so both the API layer and a
future on-device/native check can share the exact same logic, and so a unit
test can exercise it without going through the API at all.
"""


def derive_direction(start_ref: float, end_ref: float) -> str:
    """Return "NOBO" if travel runs low-to-high mile-marker, else "SOBO".

    Northbound (Springer -> Katahdin) is mile 0.0 -> mile 2189.0, an
    increasing reference; southbound is the reverse. An equal start/end
    reference has no real direction to derive - not expected for a real
    Hike, but "NOBO" is returned as a harmless default rather than raising.
    """
    return "NOBO" if start_ref <= end_ref else "SOBO"
