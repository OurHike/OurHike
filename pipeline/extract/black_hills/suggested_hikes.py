"""Black Hills Trails: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "4 trail pages: `/trails/centennial-trail-89/`, `/trails/deerfield-trail-40/`, "
        "`/trails/deerfield-lake-loop-trail-40l/`, `/trails/7th-cavalry-trail-system/` (WordPress pages dated "
        "2013–2018). (Skeptic spot-check, 2026-10-01: `wp-sitemap-posts-trails-1.xml` lists exactly these 4. "
        "They are a `trails` custom post type, so `wp/v2` may serve them as JSON; I did not test that route.)",
    ),
    where=("https://blackhillstrails.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
