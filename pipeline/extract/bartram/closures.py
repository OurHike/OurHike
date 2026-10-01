"""Bartram Trail Conference: closures, published, and not landed (coverage audit 2026-10-01, batch
q01_persist).

`openstatus` is a facility status, not a trail closure; nothing in EDW marks a closed trail segment.
Licence: USFS, public domain (17 U.S.C. 105, `usfs_licence`), a federal work → open_licence (public
domain, federal). Folder: `usfs/` (EDW layer and per-forest alerts pages, as b6 lists them).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "GIS: `https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0` "
        "`openstatus`, within 1 km of the 126.42-mi `usfs_trails` Bartram line (7 features): 8 rec sites, open "
        '4, temporarily closed 3 ("Russell Farmstead", "Appletree Group Campground", "Wine Spring Horse Camp"),'
        " none 1. Forest-wide: Chattahoochee-Oconee temporarily closed 9 / closed 2 / open 63; NFs in North "
        "Carolina temporarily closed 12 / closed 16 / none 17 / open 112. Pages: "
        "`https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts`, 30 alert links (e.g. …",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0",
        "https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts",
        "https://www.fs.usda.gov/r08/northcarolina/alerts",
        "https://bartramtrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
