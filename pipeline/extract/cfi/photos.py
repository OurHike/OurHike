"""Colorado Fourteeners Initiative: photos, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Outside the ten types: `/2025-colorado-14er-hiking-use-estimates/` publishes trail-counter use
estimates on 21 peaks, a possible input for `trail_network` popularity.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav, sitemap.",),
    where=("https://14ers.org/",),
)
