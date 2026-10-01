"""Palmetto Conservation Foundation: places, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Overlaps POIs.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The passage pages work as a trailhead directory with coordinates, and carry a Region field (Upstate, "
        "Midlands, Lowcountry).",
    ),
    where=("https://palmettoconservation.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
