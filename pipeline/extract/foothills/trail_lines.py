"""Foothills Trail Conservancy: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c5_regional_2).

The match is by name only, not by alignment. The SC State Park and Duke/Jocassee sections are in no
loaded row. Third-party ArcGIS copies exist (`an email address`, `kblazzard_WCUEDU`, the latter
built from a hiiker.app GPX), but they are personal or academic accounts and not citable under …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "On the live `EDW_TrailNFSPublish_01/MapServer/0`, `TRAIL_NAME LIKE 'FOOTHILLS%'` returns 4 segments, "
        "23.235 mi on Sumter NF (`ADMIN_ORG 0812`), and 1 segment, 5.215 mi on Nantahala NF (`0811`). Total "
        "28.45 of ~77 mi. The club's own maps are JPGs: "
        "`/wp-content/uploads/2024/01/complete-trail-map-scaled.jpg` plus 9 mini maps `MM1…MM9`.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0",
        "https://foothillstrail.org/",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
