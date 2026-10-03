"""Trailkeepers of Oregon: places, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`OCT_Section_Points` (11 named section ends, e.g. Fort Stevens State Park, Oswald West State Park). "
        '`/overnight/` is an HTML page on hiker-biker camps ("15 hiker-biker campsites on the OCT", with prices'
        " and rules). `/ferries-buses/` and `/parking-permits/` were not opened.",
    ),
    where=("https://trailkeepersoforegon.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
