"""Selma to Montgomery NHT: suggested hikes, drawn from nps/suggested_hikes.py's `nps_things_to_do and
nps_tours` (decision 54 wave 3, section C, 2026-10-04).

NPS's things to do (`/thingstodo`) and tours (`/tours`) lands once, in nps/suggested_hikes.py, read
whole, nationally, so park code `semo` is in it, and dbt assigns this folder its portion by each
row's own park list matched to nps_alerts' `park_codes` map, the one home for which folder draws on
which park (decision 34). It needs NPS_API_KEY; without it the table is withdrawn, never read as
empty (extract/_json_apis.py, 'THE KEY').

The note this replaces read, whole:

Selma to Montgomery NHT (NPS): suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Driving

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/thingstodo` (section C, 2026-10-04): landed by nps/suggested_hikes.py as nps_things_to_do and nps_tours, national; this folder's park code: semo.",
        '(the coverage audit, 2026-10-01) `NPSAPI/tours` "The Selma to Montgomery March Driving Tour" (10 stops), "Lowndes County Driving Guide" (13 stops)',
    ),
    where=(
        "https://developer.nps.gov/api/v1/thingstodo",
        "https://developer.nps.gov/api/v1/tours",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/semo/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
