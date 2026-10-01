"""Nantahala Hiking Club: closures, published, and not landed (coverage audit 2026-10-01, batch
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
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS EDW `apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0`, field "
        "`openstatus` (already in audit b6 for `usfs/`):",
        "National Forests in North Carolina, 157 rows: open 112, closed 16, temporarily closed 12, none 17.",
        "In a box around NHC's section (-83.80,34.97 to -83.40,35.36), 15 sites. Among them: Standing Indian "
        "Campground open; Standing Indian Picnic Area temporarily closed; Appletree Group Campground "
        "temporarily closed; Wine Spring Horse Camp temporarily closed; Albert Mountain Fire Tower open; Wayah "
        'Bald Tower "none".; Alerts page …',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0",
        "https://nantahalahikingclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
