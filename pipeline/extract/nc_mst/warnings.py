"""NC Mountains-to-Sea Trail (state-published layer): warnings, published, and not landed (coverage
audit 2026-10-01, batch p01_persist).

The carousel's classes (`breaking`, `warning`, `info`, `success`) are not warning-versus-closure.
Mount Mitchell's `warning` items are logistics plus a road closure, and Falls Lake's `success` is a
job advert, so every item needs the decision-7 classifier. Licence: web pages, not GIS, so 21(a)
does not reach them. The USFS page is a federal work (Reasoned). Folders: `nc-dpr/` (park alerts),
`usfs/` (NFsNC alerts), `nps/` (BLRI).

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NC DPR park pages. The `block-ncalertsblock` carousel is server-rendered. "
        "`/modules/custom/ncalert/js/ncalerts.js` (2,104 B) only animates it and fetches nothing. I sampled 5 "
        "park pages today:",
        'Mount Mitchell (on the MST): 3 items, class `warning`. "Mount Mitchell State Park does not offer '
        "transportation… Visitors who want to hike to or from Black Mountain Campground… should arrange "
        'transportation independently", and "North of the park, the Parkway is closed. There are no gas '
        'stations between Asheville & the park".',
        'Eno River (MST corridor): 1, class `breaking`, "partially closed… See Trail Statuses".',
        "Falls Lake (MST): 2, classes `info` and `success`, a closure and a job advert.",
        'Stone Mountain (MST): 1, class `warning`, "Stone Mountain Falls Closed… Stair Replacement".',
        "Jockey's Ridge: 0.",
        "The non-park fees page has 0, so the block is per-park.",
        "USFS (the MST's Pisgah and Nantahala stretches): `https://www.fs.usda.gov/r08/northcarolina/alerts` "
        "(HTML, 279,723 B, allowed by robots.txt) links 60 alerts. They include "
        "`pisgah-ranger-district-bear-canister-requirement`, "
        "`commissary-ridge-dispersed-camping-area-temporarily-closed` and "
        '`graveyard-field-camping-prohibitions-pisgah-ranger-district`, plus a "Fire Danger Status" block.',
        "NPS Blue Ridge Parkway: `developer.nps.gov/api/v1/alerts?parkCode=blri,grsm` answered 429 "
        "OVER_RATE_LIMIT on the public DEMO_KEY, so not measured today.",
        "Tried: 1 (DPR/DNCR REST, audit), 2 (AGOL `North Carolina burn ban` 4: only an NCFS 2021 app), 3 (NC "
        "OneMap: Recreation holds paddle trails only), 4 (USFS NFsNC, NPS BLRI), 5 (data.gov `mountains-to-sea "
        "trail` 2 unrelated; Socrata 0), 6 (n/a), 7 (`/jsonapi` 404, `/rss.xml` 403, `/alerts` and "
        "`/park-alerts` 404).",
    ),
    where=(
        "https://www.fs.usda.gov/r08/northcarolina/alerts",
        "https://developer.nps.gov/api/v1/alerts?parkCode=blri,grsm",
        "https://data.gov",
        "https://trails.nc.gov/",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
