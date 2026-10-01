"""El Camino Real de los Tejas NHT Association: elevation, nothing published (coverage audit
2026-10-01, batch c11_nht).

USGS 3DEP

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked: 59 WP pages via REST, nav",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://elcaminorealdelostejas.org/",
    ),
)
