"""Chesapeake Conservancy: places, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Own: none

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Decision 54, wave 3 (2026-10-04): the NPS Data API's records for this trail's park unit are registered
in nps/ and reach this club by park code, so this type is drawn from there.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "via nps `nps_api_places` (registered 2026-10-04): the NPS Data API's /places, 17,505 places nationally by its own `total` (one request with api.data.gov's public demo key), extracted once in nps/places.py; this club's portion is the places whose `relatedParks` list cajo, assigned in dbt (decision 34). It needs NPS_API_KEY in the monthly job, which does not pass it yet.",
        "`NPSAPI/places` cajo ≥14",
    ),
    where=(
        "https://developer.nps.gov/api/v1/places",
        "https://cicgis.org/arcgis/rest/services",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://chesapeakeconservancy.org/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the resource this org's data arrives in",
)
