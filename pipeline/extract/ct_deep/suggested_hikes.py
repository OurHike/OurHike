"""Connecticut DEEP: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

These are maps, not hike descriptions. Low value.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://portal.ct.gov/deep/state-parks/trail-and-camping-maps---ct-state-parks-and-forests`: 104 "
        'unique PDF map links, 15 with "trail" in the path. "CT Rail Trail Explorer" interactive map.',
    ),
    where=("https://portal.ct.gov/deep/state-parks/trail-and-camping-maps---ct-state-parks-and-forests",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
