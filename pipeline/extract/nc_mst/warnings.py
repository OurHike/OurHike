"""NC Mountains-to-Sea Trail (state-published layer): warnings, drawn from nps/warnings.py's NPS alerts
resource (decision 53, phase B, 2026-10-03).

NPS's alerts for park codes `blri` and `grsm` land once, in nps/warnings.py's `nps_alerts`, whose
sources.json entry lists them against this folder in `park_codes` (decision 34). NPS's Danger,
Caution and Information categories are the warnings half, split from the rest in dbt.

The state parks' and the national forests' pages land in their stewards' folders (decision 53 phase B,
2026-10-03): Mount Mitchell State Park's page in nc_dpr/closures.py as `nc_parks_mount_mitchell_alerts`,
and the National Forests in North Carolina's alerts page in usfs/closures.py as
`usfs_r08_northcarolina_alerts`; this note names all three. NC State Parks' RSS feed
(https://www.ncparks.gov/rss.xml) answered our agent with CloudFront's 403 'Request blocked.' on
2026-10-03 while the park pages answered 200 (the inventory, batch 3): a wall, not retried.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

The carousel's classes (`breaking`, `warning`, `info`, `success`) are not warning-versus-closure.
Mount Mitchell's `warning` items are logistics plus a road closure, and Falls Lake's `success` is a
job advert, so every item needs the decision-7 classifier. Licence: web pages, not GIS, so 21(a)
does not reach them. The USFS page is a federal work (Reasoned). Folders: `nc-dpr/` (park alerts),
`usfs/` (NFsNC alerts), `nps/` (BLRI).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=blri,grsm` (the decision 53 inventory, batch 3, 2026-10-03): 0 alerts. "
            "BLRI returned 0 today (the audit's DEMO_KEY call had 429'd). Landed by nps/warnings.py as "
            "nps_alerts."
        ),
        (
            "Landed elsewhere in decision 53 phase B (2026-10-03): nc_dpr/closures.py `nc_parks_mount_mitchell_alerts` "
            "(Mount Mitchell State Park's page) and usfs/closures.py `usfs_r08_northcarolina_alerts` (59 alert "
            "cards). https://www.ncparks.gov/rss.xml answered 403, CloudFront's 'The request could not be "
            "satisfied. Request blocked.', to our agent (inventory, batch 3): a wall, not retried."
        ),
        (
            "(coverage audit, 2026-10-01) NC DPR park pages. The `block-ncalertsblock` carousel is "
            "server-rendered. `/modules/custom/ncalert/js/ncalerts.js` (2,104 B) only animates it and fetches "
            "nothing. I sampled 5 park pages today:"
        ),
        (
            '(coverage audit, 2026-10-01) Mount Mitchell (on the MST): 3 items, class `warning`. "Mount Mitchell '
            "State Park does not offer transportation… Visitors who want to hike to or from Black Mountain "
            'Campground… should arrange transportation independently", and "North of the park, the Parkway is '
            'closed. There are no gas stations between Asheville & the park".'
        ),
        ('(coverage audit, 2026-10-01) Eno River (MST corridor): 1, class `breaking`, "partially closed… See Trail Statuses".'),
        ("(coverage audit, 2026-10-01) Falls Lake (MST): 2, classes `info` and `success`, a closure and a job advert."),
        (
            '(coverage audit, 2026-10-01) Stone Mountain (MST): 1, class `warning`, "Stone Mountain Falls Closed… '
            'Stair Replacement".'
        ),
        "(coverage audit, 2026-10-01) Jockey's Ridge: 0.",
        "(coverage audit, 2026-10-01) The non-park fees page has 0, so the block is per-park.",
        (
            "(coverage audit, 2026-10-01) USFS (the MST's Pisgah and Nantahala stretches): "
            "`https://www.fs.usda.gov/r08/northcarolina/alerts` (HTML, 279,723 B, allowed by robots.txt) links 60 "
            "alerts. They include `pisgah-ranger-district-bear-canister-requirement`, "
            "`commissary-ridge-dispersed-camping-area-temporarily-closed` and "
            '`graveyard-field-camping-prohibitions-pisgah-ranger-district`, plus a "Fire Danger Status" block.'
        ),
        (
            "(coverage audit, 2026-10-01) NPS Blue Ridge Parkway: "
            "`developer.nps.gov/api/v1/alerts?parkCode=blri,grsm` answered 429 OVER_RATE_LIMIT on the public "
            "DEMO_KEY, so not measured today."
        ),
        (
            "(coverage audit, 2026-10-01) Tried: 1 (DPR/DNCR REST, audit), 2 (AGOL `North Carolina burn ban` 4: "
            "only an NCFS 2021 app), 3 (NC OneMap: Recreation holds paddle trails only), 4 (USFS NFsNC, NPS "
            "BLRI), 5 (data.gov `mountains-to-sea trail` 2 unrelated; Socrata 0), 6 (n/a), 7 (`/jsonapi` 404, "
            "`/rss.xml` 403, `/alerts` and `/park-alerts` 404)."
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=blri,grsm",
        "https://www.ncparks.gov/state-parks/mount-mitchell-state-park",
        "https://www.ncparks.gov/rss.xml",
        "https://www.fs.usda.gov/r08/northcarolina/alerts",
        "https://data.gov",
        "https://trails.nc.gov/",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
    ),
    reason=(
        "drawn from nps/'s, nc_dpr/'s and usfs/'s resources, extracted once there (decision 34); checked names "
        "the sources this org's notices arrive in"
    ),
)
