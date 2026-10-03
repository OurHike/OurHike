"""Trail of Tears Association: trail lines, drawn from nps/'s resources (decision 34), registered on
2026-10-03.

`TRTYPE` is not evidence of walkability (finding 2)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_trail_of_tears_nht` (2,006 lines) registered in"
        " sources.json and extracted in nps/trail_lines.py.",
        '`NPSAGOL/TRTE_NHT/0`: 2,006 lines (1,467 "Standard Terra Trail", 539 "Water Trail"), edited 2026-09-17. `nps_trails`: 0',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nationaltota.com/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/TRTE_NHT/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
