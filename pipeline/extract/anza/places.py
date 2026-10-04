"""The Anza Trail Foundation: places, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Decision 54, wave 3 (2026-10-04): the NPS Data API's records for this trail's park unit are registered
in nps/ and reach this club by park code; the club's own pages are not landed.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via nps `nps_api_places` (registered 2026-10-04): the NPS Data API's /places, 17,505 places nationally by its own `total` (one request with api.data.gov's public demo key), extracted once in nps/places.py; this club's portion is the places whose `relatedParks` list juba, assigned in dbt (decision 34). It needs NPS_API_KEY in the monthly job, which does not pass it yet.",
        "Own: County Guides `https://anzahistorictrail.org/county/` (WordPress). `NPSAPI/places` juba ≥10; visitor centers 8",
    ),
    where=(
        "https://developer.nps.gov/api/v1/places",
        "https://anzahistorictrail.org/county/",
        "https://anzatrailfoundation.com/",
    ),
    reason="partly drawn from nps/'s resources (decision 34); the club's own pages are HTML, decision 54's wave 5 (a reader per site), and not landed",
)
