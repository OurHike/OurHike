"""Save Mount Diablo: closures, drawn from another folder's resource (decision 53 phase B, 2026-10-03).

This club's closures arrive through _shared/ca_state_parks/ `cdpr_park_unit_status`, each extracted
once in its steward's folder (decision 34). Its portion is assigned in dbt.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services2.arcgis.com/jeEP9c9zZoQQwtck/arcgis/rest/services/Fire_Warning_Extreme_Danger_Level_2/FeatureServer/6,
EBRPD's 132 areas that close at fire-danger Level 2, last edited 2023-08-23: a standing map, not
today's level, which EBRPD publishes elsewhere (UNKNOWN where).

Before decision 53 phase B, 2026-10-03, this note read:

Save Mount Diablo: closures, published, and not landed (coverage audit 2026-10-01, batch
p06_persist).

Licence: none_stated (licenseInfo empty). Do not load it as a live closure feed. The one row read
contradicts itself, and the data has not been edited in over two years. `@unvalidated` whether CDPR
still maintains it; CDPR's GIS team confirming would settle it. Folder: `ca-state-parks/`. The …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/ca_state_parks/ `cdpr_park_unit_status` (decision 53 phase B, 2026-10-03): `cdpr_park_unit_status` reads `CSPParkUnit_Status_DOC/FeatureServer/0`",
        '`services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services/CSPParkUnit_Status_DOC/FeatureServer/0`. It holds 281 park units, with fields `Status`, `closure_reason`, `StatusReopenDate`, `status_notes_pub` and closed/total counts for parking, restrooms, campsites and trail miles. It feeds the dashboard "California State Parks Closures Status v2.1" (`e215b21ed64447418d7bc476c447ddb0`, modified 2026-04-03). dataLastEditDate 2024-07-10. The Mount Diablo SP row reads `Status` OPEN, yet `closed_milestrail` is 200 of 200, `closed_restroooms` 15 of 15 and `closed_parkingares` 6 of 6. EBRPD\'s 470 …',
    ),
    where=("https://services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services/CSPParkUnit_Status_DOC/FeatureServer/0",),
    reason="drawn from _shared/ca_state_parks/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in",
)
