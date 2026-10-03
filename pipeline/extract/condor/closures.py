"""Condor Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

The page is a federal work (public domain, `usfs_licence`); WFIGS is none_stated (disclaimer, quoted
under `black-hills`). `seasonal_operational_status` sits in a layer we already load and is not read
by any pipeline file (grep, 2026-10-01). See Safety finds. Folders: `usfs/`, `_shared/` NIFC.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.fs.usda.gov/r05/lospadres/alerts` (HTML) holds 12 forest alerts. The ones on or near the "
        'route: "Monterey Ranger District Emergency Closure Order with Exceptions" (critical: "the Timber and '
        'Plaskett Fire Area are closed, including roads and trails described in Exhibit A", Forest Order '
        '05-07-51-26-11, start 2026-08-29); "Sespe Condor Sanctuary Closure"; "Special Closure - SBRD Storm '
        'Damage Recovery" (Order 05-07-54-26-09, 2026-09-16 to 2027-09-15); "Dry Canyon Area, Roads and Trails,'
        ' and Wilderness Closure" (Order 05-07-57-25-05). There is no feed (same probes as BH NF). …',
    ),
    where=(
        "https://www.fs.usda.gov/r05/lospadres/alerts",
        "https://condortrail.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
