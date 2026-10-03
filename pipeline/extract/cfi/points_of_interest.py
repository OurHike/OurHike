"""Colorado Fourteeners Initiative: points of interest, published, and not landed (coverage audit
2026-10-01, batch c5_regional_2).

No coordinates on the sampled pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "53 peak pages under `/peaks/<range>/<peak>/` (counted from `wp-sitemap-posts-page-1.xml`). Each gives "
        'summit elevation and rank (e.g. Bierstadt "14,065 feet (38th highest)") and the recommended trailhead.',
    ),
    where=("https://14ers.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
