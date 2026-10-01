"""Overmountain Victory Trail Association: trail lines, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Own: none

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/Overmountain_Victory_National_Historic_Trail_Official_Temp/0`: 43 lines (TrailName, "
        "TrailWebsi), edited 2025-05-30. `nps_trails`: 1 BLRI row named for the NHT",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://ovta.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
