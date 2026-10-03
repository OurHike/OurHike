"""Star-Spangled Banner NHT (NPS): trail lines, drawn from nps/'s resources (decision 34), registered on
2026-10-03.

Land and water route. Chesapeake Conservancy also has a MapJournal

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_star_spangled_banner_nht` (1 line) registered "
        "in sources.json and extracted in nps/trail_lines.py.",
        "`NPSAGOL/Sta_Spangled_Banner_National_Historic_Trail_Official_Centerline/0`: 1 line (2018-06-01). `nps_trails` STSP: 0",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/stsp/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/Sta_Spangled_Banner_National_Historic_Trail_Official_Centerline/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
