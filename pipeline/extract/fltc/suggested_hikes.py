"""Finger Lakes Trail Conference: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Passport Hikes: 3 booklets × 12 hikes, 21 `PassportHikes` waypoints. "
        "`/plan-hikes-finger-lakes-trail/special-places/`. The Cross-County Hike Series (events).",
    ),
    where=("https://fingerlakestrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
