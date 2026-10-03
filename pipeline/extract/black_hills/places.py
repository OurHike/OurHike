"""Black Hills Trails: places, drawn from usfs/'s, blm/'s and nps/'s resources (decision 54, wave 1, read
2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs `usfs_forest_boundaries` (forestorgcode '0203', the Black Hills NF) and `usfs_wilderness_areas` (Black "
        "Elk Wilderness), blm `blm_recreation_site_polygons` (Fort Meade Recreation Area among the 3,477) and nps "
        "`nps_park_boundaries`, all registered 2026-10-03. BLM_Natl_Recreation_Sites_Facilities is points_of_interest's.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recs_poly/MapServer/1",
    ),
    reason="drawn from usfs/'s, blm/'s and nps/'s resources, extracted once there (decision 34); checked names the layers",
)
