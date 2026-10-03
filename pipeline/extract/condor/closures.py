"""Condor Trail Association: closures, drawn from usfs/'s Los Padres NF alerts page (decision 53 phase
B, 2026-10-03).

The association publishes no notices: its WordPress (https://condortrail.com/wp-json/wp/v2/posts)
holds 'Hello world!' (2018) and six 2012 template posts, X-WP-Total 7. The forest does:
https://www.fs.usda.gov/r05/lospadres/alerts held 13 alerts on 2026-10-03 (information 7,
fire-restriction 5, critical 1), the critical one the Monterey Ranger District's emergency closure
order on the route. That page is the Forest Service's, read once in usfs/closures.py as
`usfs_r05_lospadres_alerts` (decision 34), and every club on the forest draws on it.

Before decision 53 phase B, 2026-10-03, this note read:

Condor Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

The page is a federal work (public domain, `usfs_licence`); WFIGS is none_stated (disclaimer, quoted
under `black-hills`). `seasonal_operational_status` sits in a layer we already load and is not read
by any pipeline file (grep, 2026-10-01). See Safety finds. Folders: `usfs/`, `_shared/` NIFC.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://www.fs.usda.gov/r05/lospadres/alerts` (HTML) holds 12
forest alerts. The ones on or near the route: "Monterey Ranger District Emergency Closure Order with
Exceptions" (critical: "the Timber and Plaskett Fire Area are closed, including roads and trails
described in Exhibit A", Forest Order 05-07-51-26-11, start 2026-08-29); "Sespe Condor Sanctuary
Closure"; "Special Closure - SBRD Storm Damage Recovery" (Order 05-07-54-26-09, 2026-09-16 to
2027-09-15); "Dry Canyon Area, Roads and Trails, and Wilderness Closure" (Order 05-07-57-25-05).
There is no feed (same probes as BH NF). …

Its `where`: https://www.fs.usda.gov/r05/lospadres/alerts https://condortrail.com/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(the decision 53 inventory, batch 5, 2026-10-03) https://www.fs.usda.gov/r05/lospadres/alerts: 200, 13 alerts in the USFS card markup (level, title, slug, start date, forest order); https://condortrail.com/wp-json/wp/v2/posts: X-WP-Total 7, none a notice.",
    ),
    where=(
        "https://www.fs.usda.gov/r05/lospadres/alerts",
        "https://condortrail.com/",
    ),
    reason="drawn from usfs/'s `usfs_r05_lospadres_alerts`, extracted once there (decision 34); the club publishes none of its own",
)
