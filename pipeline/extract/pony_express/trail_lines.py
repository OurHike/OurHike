"""National Pony Express Association: trail lines, drawn from nps/'s resources (decision 34), registered on
2026-10-03.

The Re-Ride route is roads. Do not draw it as trail

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_pony_express_nht` (1 line) registered in "
        "sources.json and extracted in nps/trail_lines.py.",
        "`NPSAGOL/POEX_NHT/0`: 1 line, 1:100k (2021-08-16). `nps_trails`: 0. The Re-Ride route "
        "`NPSAGOL/POEX_Pony_Express_ReRide_Route_2026_Layer_View`: 5,290 road segments (2026-09-23)",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nationalponyexpress.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/POEX_NHT/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
