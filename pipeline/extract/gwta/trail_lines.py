"""Great Western Trail Association: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c7_regional_4).

Correction 5. The trail is mostly motorized routes, so #1711 — Ship only hiking trails: remove NH
GRANIT, and drop USFS motorized trails nationwide may already drop much of the USFS part (R).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("68 USFS features, 440.6 mi named `GREAT WESTERN…`. 143 SGID features.",),
    where=(
        "https://apps.fs.usda.gov/fsgisx02/rest/services",
        "https://services2.arcgis.com/gdcQ6sUWKP8qwBmV/arcgis/rest/services",
        "https://americantrails.org/",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
