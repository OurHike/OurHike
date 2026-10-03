"""The Trail Foundation (Austin): elevation, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

A flat urban loop. USGS 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav and sitemap.",),
    where=("https://thetrailfoundation.org/",),
)
