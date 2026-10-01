"""Dartmouth Outing Club: places, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Marginal.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Moosilauke Ravine Lodge pages (`/facilities/moosilauke-ravine-lodge/directions`, plus a hiker-parking "
        "note on the hiking page) and Second College Grant (`/facilities/second-college-grant`). Both are "
        "pages.",
    ),
    where=("https://dartmouth.edu/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
