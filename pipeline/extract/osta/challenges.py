"""Old Spanish Trail Association: challenges, drawn from nps/challenges.py's
`nps_passport_stamp_locations` (decision 54 wave 3, section C, 2026-10-04).

NPS's passport stamp locations (`/passportstamplocations`) lands once, in nps/challenges.py, read
whole, nationally, so park code `olsp` is in it, and dbt assigns this folder its portion by each
row's own park list matched to nps_alerts' `park_codes` map, the one home for which folder draws on
which park (decision 34). It needs NPS_API_KEY; without it the table is withdrawn, never read as
empty (extract/_json_apis.py, 'THE KEY').

The note this replaces read, whole:

Old Spanish Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/passportstamplocations` (section C, 2026-10-04): landed by nps/challenges.py as nps_passport_stamp_locations, national; this folder's park code: olsp.",
        "(the coverage audit, 2026-10-01) `NPSAPI/passportstamplocations` olsp 10",
    ),
    where=(
        "https://developer.nps.gov/api/v1/passportstamplocations",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://oldspanishtrail.org/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
