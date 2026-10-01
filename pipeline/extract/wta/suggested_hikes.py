"""Washington Trails Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Pages. Trip reports are users' content and are never extracted.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/go-outside/hikes`: "4268 Hikes", each with length, elevation gain, highest point and rating. '
        "`/go-outside/map` (Leaflet).",
    ),
    where=("https://wta.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
