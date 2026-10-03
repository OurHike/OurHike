"""Randolph Mountain Club: places, drawn from usfs/'s and nh_granit/'s resources (decision 54, wave 1, read
2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs `usfs_forest_boundaries` (forestorgcode 0922, the White Mountain NF) and `usfs_wilderness_areas` (Great"
        " Gulf), and nh_granit `nh_conservation_lands` (Randolph Community Forest among the 13,502), registered "
        "2026-10-03. The WMNF's trailheads already arrive through usfs `usfs_rec_sites`.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0",
        "https://nhgeodata.unh.edu/nhgeodata/rest/services/EC/Conservation/MapServer/0",
    ),
    reason="drawn from usfs/'s and nh_granit/'s resources, extracted once there (decision 34); checked names the layers",
)
