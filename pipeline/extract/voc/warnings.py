"""Volunteers for Outdoor Colorado: warnings, nothing published (coverage audit 2026-10-01, batch
p03_persist).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The same feed and scan: no hazard notices. Tried: 1–7 as for closures.",),
    where=("https://voc.org/",),
)
