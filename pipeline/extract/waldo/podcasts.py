"""Waldo County Trails Coalition: podcasts, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic re-checked 2026-10-01: all 68 URLs in the Squarespace `sitemap.xml` (21 blog posts, 3
events, 15 pages, tags). No audio page, and no podcast/audio/listen text on `/activities`,
`/nature-activities`, `/explore-nature`, `/about` or `/home`. Stands.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked the nav.",),
    where=(
        "https://www.hillstosea.org/maps",
        "https://www.hillstosea.org/closures",
    ),
)
