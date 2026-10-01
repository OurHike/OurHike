"""USGS — The National Map: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

An aggregate that already contains USFS, which we load. This is the extreme case of #1231 —
usfs_trails and usfs_rec_sites ship nationwide (Arizona and beyond), when only the region near the
corridor was the point of registering them: about 8x USFS's count. Useful mainly as a gap-filler and
a dedup …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://partnerships.nationalmap.gov/arcgis/rest/services/USGSTrails/MapServer/0` (TrailsSegment): "
        '607,202 polylines, maxRecordCount 2,000, copyright "USGS The National Map: National Transportation '
        'Dataset; U.S. Census Bureau – TIGER/Line; U.S. Forest Service. v20260611.3". Fields include '
        "`nationaltraildesignation`, `primarytrailmaintainer`, `hikerpedestrian`, `sourceoriginator`, "
        "`sourcefeatureid`, `seasonopen`. Also "
        "`carto.nationalmap.gov/arcgis/rest/services/transportation/MapServer/37` (Trails), 591,392.",
    ),
    where=(
        "https://partnerships.nationalmap.gov/arcgis/rest/services/USGSTrails/MapServer/0",
        "https://carto.nationalmap.gov/arcgis/rest/services/transportation/MapServer/37",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
