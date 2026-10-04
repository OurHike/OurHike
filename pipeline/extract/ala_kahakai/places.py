"""Ala Kahakai Trail Association: places, its land pages in prose with no boundary or coordinate, not landed
(decision 54, wave 5, read live 2026-10-04).

Land the association acquired along the trail in Kaʻū (Waikapuna, Kaunāmano, Kāwala, Manakaʻa, Kiolakaʻa,
Kaiholena), the boundary data the `places` mart wants, published as prose: each page gives the land's acreage
and history ("The voluntary sale and acquisition of 2,317 acres at Waikapuna ...") and no shape, map block or
coordinate, so nothing here can draw the land. A boundary is never traced from a description.

Decision 54, wave 3 (2026-10-04): the NPS Data API's records for this trail's park unit are registered in nps/
and reach this club by park code.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "via nps `nps_api_places` (registered 2026-10-04): the NPS Data API's /places, 17,505 places nationally by "
        "its own `total` (one request with api.data.gov's public demo key), extracted once in nps/places.py; this "
        "club's portion is the places whose `relatedParks` list alka, assigned in dbt (decision 34). It needs "
        "NPS_API_KEY in the monthly job, which does not pass it yet.",
        "robots.txt (Squarespace's: `User-agent: *` disallows /config, /search, /api/ and the `?format=json` "
        "views, among others), then /kiolokaa-kaalualu (120,158 bytes) and /waikapuna (219,850 bytes), read "
        "2026-10-04 under lib/user_agent.py's agent: acreage and history in prose, and no map block, iframe, "
        "KML, GeoJSON or coordinate in either page.",
        "the coverage audit (2026-10-01, batch c11_nht): land pages `/waikapuna`, `/kaunamano`, `/kawala`, "
        "`/manakaa`, `/kiolokaa-kaalualu`, `/kaiholena` (Squarespace HTML; acreage and history). `NPSAPI/places` "
        "alka ≥11",
    ),
    where=(
        "https://www.alakahakaitrail.org/waikapuna",
        "https://www.alakahakaitrail.org/kiolokaa-kaalualu",
        "https://developer.nps.gov/api/v1/places",
    ),
    reason="published in prose with no boundary or coordinate: the lands are described, never drawn",
)
