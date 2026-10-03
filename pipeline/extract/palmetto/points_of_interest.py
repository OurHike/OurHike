"""Palmetto Conservation Foundation: points of interest, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Includes camping. Typed markers.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Inline markers on each passage page. On Eastatoe: Parking ×2, Trail Head ×2, Visitor Center, Fishing, "
        "Scenic Observation, Camping. Plus printed trailhead and parking lat/lon.",
    ),
    where=("https://palmettoconservation.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
