"""The Anza Trail Foundation: trail lines, drawn from nps/'s resources (decision 34), registered on
2026-10-03.

The recreation trail is the one walkable NHT dataset in the NPS set. Owner `an email address`

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_anza_recreation_trails` (578 lines), "
        "`nps_anza_nht` (3 lines) registered in sources.json and extracted in nps/trail_lines.py.",
        "`NPSAGOL/JUBA_NHT_RECREATION_TRAILS/0`: 578 lines (2026-08-11; TRSURFACE Asphalt 144, Native "
        "Material 173 …). `JUBA_NHT_` historic: 3. `JUBA_AutoTourRoute`: 1,084. `nps_trails`: 32 Anza "
        "rows in SAMO/GOGA/TUMA (LOADED fragments; a bare `%Anza%` match would claim 132 by catching "
        '"Manzanita"). `blm_trails`: 4 AZ "Anza Trail" rows (LOADED)',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://anzatrailfoundation.com/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/JUBA_NHT_RECREATION_TRAILS/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/JUBA_NHT_/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
