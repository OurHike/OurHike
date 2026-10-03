"""Carolina Mountain Club: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through usfs/ `usfs_rec_opportunities_status`, each extracted once in
its steward's folder (decision 34). Its portion is assigned in dbt.

Read and not wired (the decision 53 inventory, batch 3, 2026-10-03): the club's 'Trail Alerts' feed
(https://carolinamountainclub.org/trail-alerts/feed/) held 0 items, the page carrying hike-schedule
changes only, and its eNews category
(https://carolinamountainclub.org/wp-json/wp/v2/posts?categories=59, 5 monthly newsletters) is
newsletters, not notices. The National Forests in North Carolina's alerts page
(https://www.fs.usda.gov/r08/northcarolina/alerts, 59 alerts, Max Patch's restrictions and Graveyard
Fields' camping prohibitions among them) is the Forest Service's, read once in usfs/closures.py as
`usfs_r08_northcarolina_alerts`. NPS's GRSM and BLRI alerts land once in nps/.

Before decision 53 phase B, 2026-10-03, this note read:

Carolina Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
p01_persist).

Licence: EDW is public domain (federal work; maintainer's `usfs_licence`, 2026-09-02). The alerts
page is web prose, not GIS, and a federal work (Reasoned). Folder: `usfs/` (both); `nc-dpr/`;
`nps/`. Not CMC's. `openstatus` carries no date. @unvalidated: how soon it follows an order;
comparing it …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_rec_opportunities_status` (decision 53 phase B, 2026-10-03): `usfs_rec_opportunities_status` reads `EDW/EDW_RecreationOpportunities_01/MapServer/0`",
        "USFS EDW `https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0`, `openstatus`, counted in rough boxes around CMC's sections:",
        "A.T. Davenport Gap–Spivey Gap (-83.12,35.75 to -82.30,36.12): 35 sites. open 5, closed 10, temporarily closed 1, none 19. Closed include Harmon Den Horsecamp, Rocky Bluff Campground, Murray Branch Picnic Area and Paint Creek Campground.",
        "Art Loeb / Pisgah RD (-82.95,35.22 to -82.68,35.45): 25 sites. open 23; Sliding Rock closed; Black Mountain / South Toe River Area temporarily closed.",
        "MST Waterrock Knob–Black Mountains …",
    ),
    where=("https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0",),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; and from its alerts page, `usfs_r08_northcarolina_alerts`",
)
