"""Bureau of Land Management: points of interest, published, and not landed (coverage audit 2026-10-01,
batch b6_federal).

"Campsite - Primitive" may be dispersed camping. It needs the review
`usfs_dispersed_camping_holdback` records before any of it ships (Reasoned). What "Water Staging
Area" means is unknown, so do not map it to water. Skeptic: the Oregon fire water sources are water
for firefighting. Like Water …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recs_pts/MapServer`, one point layer per"
        " type: Potable Water (11) 61; Group Shelter (5) 36; Cabin (19) 10; Trail Head (14) 1,256; Parking Area"
        " (8) 794; Restroom (12) 1,411; Campground (2) 583; Campsite - Developed (3) 1,462; Campsite - "
        "Primitive (4) 1,386; Scenic Overlook (13) 381; Ranger Station/Field Office (0) 65; Water Staging Area "
        "(16) 30. Also `BLM_Natl_Recreation/MapServer/3` (all rec sites, 10,241) and "
        "`BLM_Natl_Recreation_Sites_Facilities/MapServer/0` (RIDB-sourced facilities, 1,261, "
        "`max(LastUpdatedDate)` 2026-09-29) and …",
    ),
    where=(
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recs_pts/MapServer",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recreation/MapServer/3",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recreation_Sites_Facilities/MapServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
