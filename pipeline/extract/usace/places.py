"""US Army Corps of Engineers: places, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("RIDB `/recareas` (key) or the bulk export.",),
    where=("https://usace.army.mil/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
