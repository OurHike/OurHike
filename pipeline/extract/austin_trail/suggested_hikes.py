"""The Trail Foundation (Austin): suggested hikes, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav, the 20-sitemap `sitemap_index.xml`, REST searches.",),
    where=("https://thetrailfoundation.org/",),
)
