"""NC High Peaks Trail Association: warnings, nothing published (coverage audit 2026-10-01, batch
p09_persist).

Folders: `usfs/` (an alerts page; b6 lists the USFS channels), `nps/`, `nc-dpr/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The land managers' channels: National Forests in North Carolina alerts, "
        "`https://www.fs.usda.gov/r08/northcarolina/alerts` (HTML), 60 alert pages typed Critical, Caution, "
        "Information or Fire Restriction. They include `pisgah-ranger-district-bear-canister-requirement`, "
        '`commissary-ridge-dispersed-camping-area-temporarily-closed` ("an increase in bear activity"), '
        "`helene-closures`, and Appalachian Ranger District orders (Max Patch, Paint Rock, Shope Creek). No "
        "slug names the Black Mountains; only the slugs were checked, not the alert bodies. NPS alerts API, "
        "BLRI: 0 today. NC State Parks banners …",
    ),
    where=(
        "https://www.fs.usda.gov/r08/northcarolina/alerts",
        "https://nchighpeaks.org/",
    ),
)
