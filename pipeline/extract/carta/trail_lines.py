"""El Camino Real de Tierra Adentro Trail Association (CARTA): trail lines, published, and not landed
(coverage audit 2026-10-01, batch c11_nht).

Own: UNKNOWN

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAGOL/ELCA_NHT/0`: 5 lines, 1:100k (2021-08-02). `nps_trails`: 0",),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://caminorealcarta.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
