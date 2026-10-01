"""AZGeo Data Hub: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Batch c10 owns the check.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Format page: `aztrail.org/explore/day-hikers-guide/` (org_channels 2026-09-29; not reopened).",),
    where=("https://aztrail.org/explore/day-hikers-guide/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
