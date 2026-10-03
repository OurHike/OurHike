"""Condor Trail Association: warnings, drawn from usfs/'s Los Padres NF alerts page (decision 53 phase
B, 2026-10-03).

The association publishes no notices: its WordPress (https://condortrail.com/wp-json/wp/v2/posts)
holds 'Hello world!' (2018) and six 2012 template posts, X-WP-Total 7. The forest does:
https://www.fs.usda.gov/r05/lospadres/alerts held 13 alerts on 2026-10-03 (information 7,
fire-restriction 5, critical 1), the critical one the Monterey Ranger District's emergency closure
order on the route. That page is the Forest Service's, read once in usfs/closures.py as
`usfs_r05_lospadres_alerts` (decision 34), and every club on the forest draws on it.

Before decision 53 phase B, 2026-10-03, this note read:

Condor Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

Same licences. The PSW model is a research product; its licenseInfo is an HTML block that was not
read in full. Do not render it as a current hazard (Reasoned). LPFA's posts remain a non-GIS lead,
already in the audit.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Same LPNF alerts page. Fire-restriction alerts: "Los Padres
Fire Use and Firearm Restrictions" ("Prohibits building, maintaining, attending, or using a fire,
campfire, or stove fire… except in the Designated Campfire Use Sites"), "Santa Barbara Front Country
Fire Use Restrictions", "West Cuesta Fire Use Restrictions", and "San Carpoforo Beach Prohibition of
Overnight Camping and Campfires". There are also "Santa Lucia Ranger District Storm Damage Recovery"
and "Occupancy and Use Forest Order" (stay limits). WFIGS perimeters as for closures. USFS PSW
Research Station publishes …

Its `where`: https://apps.fs.usda.gov/arcx/rest/services https://condortrail.com/

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
