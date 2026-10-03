"""Mazamas: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

A page, not machine-readable. The terms are unknown (see the flags above).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/hikelist/`: 161 hikes, each with miles, elevation gain, driving miles and a trailhead-fee flag, in "
        'an HTML list, e.g. "Angels Rest 4.6 miles 1,540 feet 42 miles, no". `/streetrambles/routes-maps/` has '
        '"A COLLECTION OF 50 STREET RAMBLE HIKES" (urban walks, Sept 2019). `/climbroutes/` lists climbing '
        "routes by region.",
    ),
    where=("https://mazamas.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
