"""Selma to Montgomery NHT (NPS): trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c11_nht).

Also available: `NPSAGOL/Selma_to_Montgomery_National_Historic_Trail_Official/0`, 1 line (2017), the
54-mile march route along US-80, a highway. It must not draw as a walkable trail

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`nps_trails` UNITCODE SEMO: 4 features ("Walking Path")',),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/semo/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
