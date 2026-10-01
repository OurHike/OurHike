"""El Camino Real de los Tejas NHT Association: suggested hikes, published, and not landed (coverage
audit 2026-10-01, batch c11_nht).

Private land, by reservation. Any listing must carry that

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: `/brazos-region/` "Walk the Ranchería Grande", "2.2 miles round trip on private property", '
        'reservation required, "watch out for holes, sticks, snakes". `NPSAPI/thingstodo` elte 10 ("Hike on El '
        'Camino Real de los Tejas")',
    ),
    where=("https://elcaminorealdelostejas.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
