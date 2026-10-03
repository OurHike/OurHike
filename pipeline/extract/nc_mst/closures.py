"""NC Mountains-to-Sea Trail (state-published layer): closures, drawn from nps/warnings.py's NPS alerts
resource (decision 53, phase B, 2026-10-03).

NPS's alerts for park codes `blri` and `grsm` land once, in nps/warnings.py's `nps_alerts`, whose
sources.json entry lists them against this folder in `park_codes` (decision 34). NPS's `Park
Closure` category is the closures half, split from the rest in dbt; a Park Closure most often closes
a facility or a road rather than a trail, and no alert carries geometry, so it never sets
`obstructs_trail` alone.

The state parks' and the national forests' pages land in their stewards' folders (decision 53 phase B,
2026-10-03): Mount Mitchell State Park's page in nc_dpr/closures.py as `nc_parks_mount_mitchell_alerts`,
and the National Forests in North Carolina's alerts page in usfs/closures.py as
`usfs_r08_northcarolina_alerts`; this note names all three. NC State Parks' RSS feed
(https://www.ncparks.gov/rss.xml) answered our agent with CloudFront's 403 'Request blocked.' on
2026-10-03 while the park pages answered 200 (the inventory, batch 3): a wall, not retried.
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
            "(coverage audit, 2026-10-01) Format page. Park pages carry an alert block (`block-nc-alert-block` in "
            "the HTML of `/state-parks/crowders-mountain-state-park/trails`). The sitemap (733 URLs) has closure "
            "news pages, e.g. `/state-parks/dismal-swamp-state-park/news/closure-bridge-repairs`. `rss.xml` "
            "returns 403."
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=blri,grsm",
        "https://www.ncparks.gov/state-parks/mount-mitchell-state-park",
        "https://www.ncparks.gov/rss.xml",
        "https://www.fs.usda.gov/r08/northcarolina/alerts",
        "https://trails.nc.gov/",
    ),
    reason=(
        "drawn from nps/'s, nc_dpr/'s and usfs/'s resources, extracted once there (decision 34); checked names "
        "the sources this org's notices arrive in"
    ),
)
