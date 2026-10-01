"""Oregon Natural Desert Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Pages. The `hike` type is not exposed in `/wp/v2/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The `hike` custom post type: 24 pages in `hike-sitemap.xml` (e.g. `/hike/big-indian-gorge/`). Posts "
        '`/oregon-desert-trail-day-hikes/` ("21 Day Hikes") and `/oregon-desert-trail-loop-hikes/`.',
    ),
    where=("https://onda.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
