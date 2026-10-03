"""Black Hills Trails: trail lines, drawn from another folder's resource (coverage audit 2026-10-01,
batch c5_regional_2).

The remaining Centennial miles cross Custer SP, Wind Cave NP (`nps_trails` is loaded; the match was
not measured) and Bear Butte SP. The ArcGIS item named "Black Hills Trails" belongs to
`jmccune_personal`, an unrelated personal account.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`TRAIL_NAME LIKE 'CENTENNIAL%' AND ADMIN_ORG LIKE '0203%'` returns 14 segments, 84.654 mi on Black "
        "Hills NF. The club's own map page `/maps/centennial/` has no iframe, no data URL and no map script (it"
        " renders no map). The club also links `/wp-content/uploads/2017/06/7th-Cavalry-Map.pdf` and a mirror "
        "of the USFS Centennial guide (`…/2013/11/stelprdb5194547.pdf`).",
    ),
    where=("https://blackhillstrails.org/",),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
