"""El Camino Real de los Tejas NHT Association: points of interest, published, and not landed (coverage
audit 2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NTIR POIs `elte` 49. `NPSAGOL/NTIR_ELTE_Texas_Historical_Markers_Within_1_Mile_Buffer`: 1,077 (Texas "
        "Historical Commission markers, 2021)",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://elcaminorealdelostejas.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
