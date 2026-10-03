"""Sierra Buttes Trail Stewardship: points of interest, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

A planning inventory: `Comments` reads like "Permitting unknown, need to meet with PNF". Load the
facts and drop the planning notes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Connected Community Trailheads", `CC_Trailheads/FeatureServer/0`: 26 points with `Lat`, `Lon`, '
        '`TH_Category` and `Amenities_Existing` (e.g. "Double pit toilet, pull through area, parking"). Data '
        "last edited 2025-06-25.",
    ),
    where=("https://services6.arcgis.com/t5asxkRF7xoBwgqv/arcgis/rest/services/CC_Trailheads/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
