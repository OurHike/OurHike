"""Nantahala Hiking Club: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through usfs/ `usfs_rec_opportunities_status`, each extracted once in
its steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://us7.campaign-archive.com/feed?u=925ff9fcd932406a399b6bcf3&id=e76f54b460 (rss - robots.txt
disallows it, so not to be fetched); https://nantahalahikingclub.org/newsletters/ (html_page).

Before decision 53 phase B, 2026-10-03, this note read:

Nantahala Hiking Club: closures, published, and not landed (coverage audit 2026-10-01, batch
p06_persist).

Licence: EDW copyrightText is a no-warranty disclaimer, public domain under 17 U.S.C. §105
(maintainer, 2026-09-02, `usfs_licence`). The alerts page is web prose, not GIS, so 21(a) does not
reach it. It is a federal work (Reasoned).; Folder: `usfs/`.; `openstatus` has no date field.
`@unvalidated` …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_rec_opportunities_status` (decision 53 phase B, 2026-10-03): `usfs_rec_opportunities_status` reads `EDW/EDW_RecreationOpportunities_01/MapServer/0`",
        "USFS EDW `apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0`, field `openstatus` (already in audit b6 for `usfs/`):",
        "National Forests in North Carolina, 157 rows: open 112, closed 16, temporarily closed 12, none 17.",
        'In a box around NHC\'s section (-83.80,34.97 to -83.40,35.36), 15 sites. Among them: Standing Indian Campground open; Standing Indian Picnic Area temporarily closed; Appletree Group Campground temporarily closed; Wine Spring Horse Camp temporarily closed; Albert Mountain Fire Tower open; Wayah Bald Tower "none".; Alerts page …',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0",
        "https://nantahalahikingclub.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in; the org's own non-ArcGIS sources are listed in the docstring, still to wire",
)
