"""AMC Delaware Valley Chapter: elevation, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav and the WP page list (`/wp-json/wp/v2/pages`).",),
    where=("https://amcdv.org/",),
)
