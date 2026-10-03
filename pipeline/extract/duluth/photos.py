"""City of Duluth Open Data: photos, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No photo items in the `agomainadmin` keyword scan.",
        "Skeptic adds: all 360 org items were scanned. The only photo-like items are `Pictometry2016` (St. "
        "Louis County oblique imagery, served from `gis.stlouiscountymn.gov`), a `DuluthStreetNamesPhoto` map "
        "service and a police patch image. None is a photo of a trail feature.",
    ),
    where=("https://gis.stlouiscountymn.gov",),
)
