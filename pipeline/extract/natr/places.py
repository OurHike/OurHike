"""Natchez Trace NST (NPS-administered): places, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Deduplicate the 21 shared with `natt` against the NST unit's own places.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Decision 54, wave 3 (2026-10-04): the NPS Data API's records for this trail's park unit are registered
in nps/ and reach this club by park code, so this type is drawn from there.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "via nps `nps_api_places` (registered 2026-10-04): the NPS Data API's /places, 17,505 places nationally by its own `total` (one request with api.data.gov's public demo key), extracted once in nps/places.py; this club's portion is the places whose `relatedParks` list natr (and natt), assigned in dbt (decision 34). It needs NPS_API_KEY in the monthly job, which does not pass it yet.",
        "API `/places`: 42. `/visitorcenters`: 4.",
        "Skeptic: not reproduced. `/places?parkCode=natr` returns `total` 125 today (all 125 fetched): 101 list only `natr`, 21 also list `natt` (Natchez Trace National Scenic Trail), and 3 also list `trte`.",
    ),
    where=(
        "https://developer.nps.gov/api/v1/places",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/natr/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the resource this org's data arrives in",
)
