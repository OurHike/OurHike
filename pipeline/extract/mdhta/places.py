"""Maah Daah Hey Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "19 trailhead pages (`wp-sitemap-posts-trailheads-1.xml`), the same rows as the POI trailheads. The "
        "FAQ's campground-distance table and its 4 registered support providers. `/white-butte-2/` (North "
        "Dakota's high point).",
    ),
    where=("https://mdhta.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
