"""Colorado Trail Foundation: places, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`https://coloradotrail.org/trail/segments-of-the-ct/`: segment trailheads and nearby towns (search snippet).",),
    where=("https://coloradotrail.org/trail/segments-of-the-ct/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
