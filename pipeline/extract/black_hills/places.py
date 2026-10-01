"""Black Hills Trails: places, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

Licences: USFS copyrightText "USDA Forest Service Enterprise Map Services Program, Enterprise Data
Warehouse": public domain, federal. NPS LRD licenseInfo is a disclaimer ("Property ownership data is
compiled from deeds, plats, surveys…"): public domain, federal. CityParkData accessInformation …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS `https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0` "
        "forestorgcode '0203': 1 polygon (1,537,116 ac). `EDW_Wilderness_02/MapServer/0` \"Black Elk "
        'Wilderness": 1 (13,534 ac). BLM `recreation/BLM_Natl_Recs_poly/MapServer/0` in the Fort Meade '
        'envelope: 7 polygons, including "Fort Meade Recreation Area ACEC" (SRMA) and Alkali Creek Campground. '
        '`BLM_Natl_Recreation_Sites_Facilities/MapServer/1` "Fort Meade Recreation Area": 1. NPS …',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recreation_Sites_Facilities/MapServer/1",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
