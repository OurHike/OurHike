"""Cumberland Trail / Tennessee State Parks: elevation, published as lidar DEM tiles, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. The Tennessee lidar tile index is a vector index of DEM and point-cloud downloads,
not elevations. Not re-read for decision 54.

Licence:; • TN lidar: none_stated, a disclaimer: "The State of Tennessee makes no representation or
warranty as to the accuracy of this map… The user accepts this map on an 'AS IS' basis…".; • The
CTSST app's `licenseInfo` carries an explicit restriction (quoted at the end of this file). The same
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "TN lidar portal (`lidar.tn.gov`, a Hub run by TN Strategic Technology Solutions):",
        '`services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services/TN_2015_Cumberland_27_C…` "State of '
        'Tennessee LiDAR Coverage Map 2015 Cumberland 27 County QL2 Tile Index" (item `6bd3b0b8…`). 10,868 '
        'tiles, each with `DEM_Download` and `Point_Cloud_Download` links (Google Drive). Snippet: "covering 27'
        " counties in Tennessee over the Cumberland Plateau region. Updated May 2024 with Point Cloud and DEM "
        'download links."',
        '"Tennessee USGS 3DEP Projects" (item `d5d7c7b7…`): 13 project polygons with DEM, contour …',
    ),
    where=(
        "https://lidar.tn.gov",
        "https://services1.arcgis.com/YuVBSS7Y1of2Qud1/arcgis/rest/services/TN_2015_Cumberland_27_C",
        "https://services5.arcgis.com/bPacKTm9cauMXVfn/arcgis/rest/services",
        "https://tnmap.tn.gov/arcgis/rest/services",
        "https://tnstateparks.com",
    ),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
