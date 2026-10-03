"""El Camino Real de Tierra Adentro Trail Association (CARTA): trail lines, drawn from nps/'s resources
(decision 34), registered on 2026-10-03.

Own: UNKNOWN

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_el_camino_tierra_adentro_nht` (5 lines) "
        "registered in sources.json and extracted in nps/trail_lines.py.",
        "`NPSAGOL/ELCA_NHT/0`: 5 lines, 1:100k (2021-08-02). `nps_trails`: 0",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://caminorealcarta.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ELCA_NHT/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
