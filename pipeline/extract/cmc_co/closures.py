"""Colorado Mountain Club: closures, nothing published (coverage audit 2026-10-01, batch p06_persist).

Kept NOT_PUBLISHED rather than flipped via a land manager. CMC is an UMBRELLA with no trail of its
own, so crediting the COTREX layer to it would count that layer twice.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "CMC publishes no closure item, and its hosted org is gated. A statewide channel exists, but it is "
        "CPW's: `SCs_All_COTREX_Sept2025_Final` (128 seasonal wildlife closures), already recorded by audits b7"
        " and c13 for `_shared/cotrex`. ArcGIS Online `COTREX closures` 10 and `COTREX alerts` 4. Both include "
        "Boulder County's `BCPOS Trail Segment Closures (Public)` (`aa4ef2969df9456d82d251a02ea39684`), which "
        "belongs to Boulder County. Tried: 1, 2, 3 (COTREX), 4 (CPW, Boulder County), 5 (data.gov 0, Socrata "
        "0), 6 and 7 (not fetched).",
    ),
    where=("https://data.gov",),
)
