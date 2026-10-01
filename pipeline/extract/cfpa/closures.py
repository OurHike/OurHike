"""Connecticut Forest & Park Association: closures, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

RSS for change detection, the page for the full list. The ArcGIS notices layer is five years stale.
Do not use it. The NET site's CT closures link straight here. Skeptic spot-check: the feed returns
200 with 10 items. The newest is "Ragged Mountain Preserve, Storm Damage CLEARED" (2026-07-17), then
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://ctwoodlands.org/trail-notices/`: 31 notices (2018-07-19 to 2026-07-17). RSS "
        "`https://ctwoodlands.org/trail-notices/feed/` returns the newest 10. They are mostly relocations, plus"
        ' "Trails Closed" (2024-12-20). ArcGIS `TrailNotices`: 30 points, last edit 2021-08-20.',
    ),
    where=(
        "https://ctwoodlands.org/trail-notices/",
        "https://ctwoodlands.org/trail-notices/feed/",
        "https://ctwoodlands.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
