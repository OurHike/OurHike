"""Appalachian Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Page. Skeptic spot-check: `/resources/itineraries/` returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.outdoors.org/resources/itineraries/`: Presidential Traverse, Pemigewasset Loop, "
        "4000-footers, regional day hikes, the A.T., Maine Woods and more. NET `find-a-hike/` renders by "
        "JavaScript (0 results server-side).",
    ),
    where=(
        "https://www.outdoors.org/resources/itineraries/",
        "https://outdoors.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
