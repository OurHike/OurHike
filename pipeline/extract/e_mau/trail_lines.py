"""E Mau Na Ala Hele: trail lines, drawn from nps/'s resources (decision 34), registered on 2026-10-03.

Own: none

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_ala_kahakai_kohala_hema` (14 lines), "
        "`nps_ala_kahakai_alanui_aupuni` (1 line), `nps_ala_kahakai_kaawaloa` (1 line), "
        "`nps_ala_kahakai_kiholo_puako` (2 lines) registered in sources.json and extracted in "
        "nps/trail_lines.py.",
        "Same ALKA layers as `ala-kahakai`",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://emaunaalahele.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ALKA_Story_Maps/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ALKA_Story_Maps/FeatureServer/1",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ALKA_Story_Maps/FeatureServer/2",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ALKA_Story_Maps/FeatureServer/3",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
