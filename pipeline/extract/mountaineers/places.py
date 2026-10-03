"""The Mountaineers: places, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Count and format were not measured.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Routes & Places trailhead records appear in a search index, e.g. "
        "`/activities/routes-places/cougar-mountain-harvey-manning-trailhead`.",
    ),
    where=("https://mountaineers.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
