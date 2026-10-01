"""Dartmouth Outing Club: points of interest, drawn from another folder's resource (coverage audit
2026-10-01, batch c1_at_clubs_north).

The cabins are reservation-only rentals, mostly off the A.T. They are of low value to a walk-in
hiker (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "ATC (code 3): shelters 7, campsites 5, privies 9, parking 11, viewpoints 37, bridges 12. DOC also "
        "lists 18 cabins on `https://outdoors.dartmouth.edu/facilities/cabins/find-cabin` (page; capacity "
        'filter 6–49; amenities include "Piped water" and "Primitive outhouse").',
    ),
    where=("https://outdoors.dartmouth.edu/facilities/cabins/find-cabin",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
