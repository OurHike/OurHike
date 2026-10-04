"""Selma to Montgomery NHT (NPS): points of interest, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Two of the visitor centers are closed today, per alerts

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Decision 54, wave 3 (2026-10-04): the NPS Data API's records for this trail's park unit are registered
in nps/ and reach this club by park code; the club's own pages are not landed.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via nps `nps_api_campgrounds` (registered 2026-10-04): the NPS Data API's /campgrounds, 665 nationally by its own `total`, extracted once in nps/points_of_interest.py; this club's portion is the campgrounds whose `parkCode` is semo, assigned in dbt (decision 34). It needs NPS_API_KEY in the monthly job, which does not pass it yet.",
        "the NPS Data API's /visitorcenters is not registered: it answered 429 OVER_RATE_LIMIT on api.data.gov's public demo key on 2026-10-04, so nothing of it was read (decision 54, wave 3).",
        "`NPSAPI/visitorcenters` semo 4 (Lowndes, Montgomery, Selma Interpretive Centers; Temporary Selma Welcome Center). `NPSAPI/campgrounds` semo 3 (Paul Grist State Park, Prairie Creek, Gunter Hill), with lat/long",
    ),
    where=(
        "https://developer.nps.gov/api/v1/campgrounds",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/semo/",
    ),
    reason="partly drawn from nps/'s resources (decision 34); the club's own pages are HTML, decision 54's wave 5 (a reader per site), and not landed",
)
