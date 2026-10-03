"""Overmountain Victory Trail Association: trail lines, drawn from nps/'s resources (decision 34),
registered on 2026-10-03.

Own: none

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_overmountain_victory_nht` (43 lines) registered"
        " in sources.json and extracted in nps/trail_lines.py.",
        "`NPSAGOL/Overmountain_Victory_National_Historic_Trail_Official_Temp/0`: 43 lines (TrailName, "
        "TrailWebsi), edited 2025-05-30. `nps_trails`: 1 BLRI row named for the NHT",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://ovta.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/Overmountain_Victory_National_Historic_Trail_Official_Temp/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
