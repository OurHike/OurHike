"""Arizona Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

The fire-restriction polygon is stale. Do not treat it as current. Skeptic spot-check:
`/explore/hazards-considerations/` returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'From the same category: "Danger: Concertina Wire Added to Fence at Southern Terminus" (2025-11-05), '
        '"Camping Restrictions Within Washington Fire Burn Area" (2025-08-27), "Camping Ban Near Flagstaff '
        'Impacts Passages 31–34" (2023). Page `/explore/hazards-considerations/` (static). ArcGIS '
        "`USFS_Camping_and_Campfire_Restricted_Area`: 1 polygon, last edit 2023-05-09.",
    ),
    where=("https://aztrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
