"""MassGIS (Bureau of Geographic Information): elevation, published as a lidar DEM and 1-ft contours,
not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Contours are vectors, so decision 35 does not cover them, but no mart reads them
and they are background-map material: decision 54's wave 1 registers none, and loading them is the
maintainer's call (decided 2026-10-03). NOT RE-READ: arcgisserver.digital.mass.gov answered its
robots.txt with 502 Bad Gateway on 2026-10-03, and RFC 9309 reads a server error there as a full
disallow, so nothing on that host was fetched.

Built from the same 2013–2021 lidar collections 3DEP serves (Reasoned). Goes in `_shared/`, low
priority.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`LiDAR/DEM_lidar_2013to2021_32bitFloat/ImageServer` (pixel 1.38 in EPSG:3857), "
        "`LiDAR/ShadedRelief_LiDAR_2013to2021`, `AGOL/Contours_1Foot`, `AGOL/Lidar_DEM_Mosaic_Index`.",
    ),
    where=("https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/LiDAR/DEM_lidar_2013to2021_32bitFloat/ImageServer",),
    reason=(
        "raster and vector contours, not landed: decision 35 lands no raster, and decision 54's wave 1 "
        "registers no contours, which are the maintainer's call; checked gives the measured counts"
    ),
)
