"""Arizona Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Skeptic spot-check: `Gateway_Community_Points/0` = 22, last edit 2025-12-28.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../Gateway_Community_Points/FeatureServer/0`: 22 points with `Weblink`. The page "
        "`/explore/gateway-communities/` lists 20 towns. Layer `/6` AZT Passages Segments: 138 polygons. "
        "`Land_Ownership_within_10_miles_of_AZ_Trail`.",
    ),
    where=("https://aztrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
