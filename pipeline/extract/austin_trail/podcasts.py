"""The Trail Foundation (Austin): podcasts, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("REST search `podcast` returns 0 results.",),
    where=("https://thetrailfoundation.org/",),
)
