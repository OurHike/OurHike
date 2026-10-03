"""El Camino Real de los Tejas NHT Association: places, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: `/south-texas-region/`, `/san-antonio-goliad-region/`, `/brazos-region/`, "
        "`/east-texas-caddo-region/` (HTML, sites with addresses). `NPSAPI/places` elte ≥20",
    ),
    where=("https://elcaminorealdelostejas.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
