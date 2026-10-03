"""Wisconsin DNR Open Data: elevation, published as lidar DEMs, contours and elevation points, not
landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Contours are vectors, so decision 35 does not cover them, but no mart reads them
and they are background-map material: decision 54's wave 1 registers none, and loading them is the
maintainer's call (decided 2026-10-03). One of its contour services alone serves 7,002,385 elevation
points (re-counted 2026-10-03).

A real statewide lidar DEM. Whether it adds anything over the shared USGS elevation source for
Wisconsin is @unvalidated: 3DEP may carry the same county lidar. What would settle it is comparing
the two sources' tile dates and resolutions for one county. Not a club-folder load. If anything, it
is …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `arcgis_image/rest/services/DW_Elevation` lists 13 services, 3 MapServers "
        "(`EN_Contour_from_LiDAR_2_ft`, `_5_ft`, `_10_ft`) and 10 ImageServers (DEMs, hillshades, slopes); "
        "`EN_Contour_from_LiDAR_10_ft/MapServer/0` is 'Elevation Points', 7,002,385 points with a `Z` field",
        "`dnrmaps.wi.gov` folders (26) and `LF_DML` (17 services): no elevation product.",
        "Skeptic adds (Measured): `https://dnrmaps.wi.gov/arcgis_image/rest/services/DW_Elevation/` holds 13 "
        'services: `EN_DEM_from_LiDAR` (ImageServer, F32, 0.3-unit pixels, "LiDAR-derived DEMs for all counties'
        ' in Wisconsin and along the shore of Lake Michigan, last updated May 7, 2024", county lidar plus NOAA '
        "topobathy), `EN_DEM_from_LiDAR_Feet`, `EN_Contour_from_LiDAR_2_ft`/`_5_ft`/`_10_ft`, hillshades and "
        "slope rasters. The third root, `/arcgis2`, has 38 folders, also unwalked by the first pass.",
    ),
    where=(
        "https://dnrmaps.wi.gov/arcgis_image/rest/services/DW_Elevation/",
        "https://dnrmaps.wi.gov/arcgis/rest/services",
    ),
    reason=(
        "raster and vector contours, not landed: decision 35 lands no raster, and decision 54's wave 1 "
        "registers no contours, which are the maintainer's call; checked gives the measured counts"
    ),
)
