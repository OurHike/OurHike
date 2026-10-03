"""Upper Valley Trails Alliance: podcasts, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic re-checked 2026-10-01: `uvtrails.org/wp-json/wp/v2/search?search=podcast` still 0 (retried
through the connection resets); categories are only `uncategorized` (74); a web search found no UVTA
podcast. Stands.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('WP search for "podcast" returned 0. Nav has none.',),
    where=(
        "https://uvtrails.org/wp-json/wp/v2/search?search=podcast",
        "https://uvtrails.org/",
    ),
)
