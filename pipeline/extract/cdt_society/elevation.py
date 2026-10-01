"""Continental Divide Trail Society: elevation, could not be told (coverage audit 2026-10-01, batch
c10_nst_rest).

USGS 3DEP covers the corridor whatever the answer.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Same.",),
    where=("https://cdtsociety.org/",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
