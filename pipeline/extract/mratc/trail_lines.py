"""Mount Rogers Appalachian Trail Club: trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c3_at_clubs_south).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`centerline` (97 features, 59.8 mi under `MRATC`) and `side_trails` (38). The Iron Mountain Trail "
        "arrives via `usfs_trails` (`TRAIL_NAME = 'IRON MOUNTAIN'` exists under `admin_org 080814`). MRATC's "
        "own geometry: none. The detour map it links to is ATC's.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://mratc.org/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
