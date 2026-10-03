"""NC Mountains-to-Sea Trail (state-published layer): closures, drawn from nps/warnings.py's NPS alerts
resource (decision 53, phase B, 2026-10-03).

NPS's alerts for park codes `blri` and `grsm` land once, in nps/warnings.py's `nps_alerts`, whose
sources.json entry lists them against this folder in `park_codes` (decision 34). NPS's `Park
Closure` category is the closures half, split from the rest in dbt; a Park Closure most often closes
a facility or a road rather than a trail, and no alert carries geometry, so it never sets
`obstructs_trail` alone.

The inventory also found a web page, an RSS feed for this club, which other phase B readers take; if
one lands for this type it takes this file, and this note becomes a line in its docstring.
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
            "(coverage audit, 2026-10-01) Format page. Park pages carry an alert block (`block-nc-alert-block` in "
            "the HTML of `/state-parks/crowders-mountain-state-park/trails`). The sitemap (733 URLs) has closure "
            "news pages, e.g. `/state-parks/dismal-swamp-state-park/news/closure-bridge-repairs`. `rss.xml` "
            "returns 403."
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=blri,grsm",
        "https://trails.nc.gov/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
