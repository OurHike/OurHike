"""AZGeo Data Hub: closures, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

This goes to `ata/closures.py`. The order belongs to the Forest Service.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The ATA closures RSS `https://aztrail.org/category/closures-reroutes/feed/` answered HTTP 200 (12,033 "
        "bytes) today; it was listed in org_channels 2026-09-29. `USFS_Camping_and_Campfire_Restricted_Area/0`:"
        " 1 Coconino NF order, last edit 2023-05-09 (stale).",
    ),
    where=("https://aztrail.org/category/closures-reroutes/feed/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
