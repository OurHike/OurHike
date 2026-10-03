"""Bay Area Ridge Trail Council: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

Section text is a 2019 Wilderness Press guidebook excerpt (see flags).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WordPress REST `/wp-json/wp/v2/trail-section`: 86 posts, each with distance, from/to and land manager."
        ' Category "Curated Adventures" has 33 posts. `/trip-planning-tools/` lists multi-day treks and '
        "bikepacking plans. There are 92 regional map PDFs (2019) on `/trail-maps/`.",
    ),
    where=("https://ridgetrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
