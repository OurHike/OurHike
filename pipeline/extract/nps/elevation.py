"""National Park Service: elevation, published as park contour sets and DEMs, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Contours are vectors, so decision 35 does not cover them, but no mart reads them
and they are background-map material: decision 54's wave 1 registers none, and loading them is the
maintainer's call (decided 2026-10-03). GRSM's 40-ft contours, the only set the audit found on the
A.T. corridor, are 121,095 lines in 29 layers (coverage audit 2026-10-01); nps_poi/elevation.py
notes the same item, which one folder would hold.

Park by park, and mostly derived from USGS or NGS lidar, so 3DEP (`_shared/usgs`) stays the better
source and none of this is worth loading first. GRSM's contours are the only ones found on the A.T.
corridor. A note saying "NPS publishes no elevation" would have been false.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `GRSM_CONTOURS/FeatureServer` (item 9bdc57b4448e4bc1bd39a0ac024e072b) still "
        "lists 29 layers; the per-layer counts were not re-read",
        "First pass: `https://mapservices.nps.gov/arcgis/rest/services?f=json` has five folders and no DEM or "
        "profile. That is still true.",
        "Skeptic, Measured 2026-10-01: the ArcGIS Online search `orgid:fBc8EJBxQRMcHlei AND (elevation OR DEM "
        "OR contour OR contours OR hillshade)` returned 312 items. Examples: "
        "`https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_CONTOURS/FeatureServer` "
        '("Great Smoky Mountains National Park 40 ft Contours", 29 quad layers, polyline). Its layer 6, '
        '"Clingmans Dome 40 ft Contours", holds 6,937 lines, `dataLastEditDate` 2025-03-13. …',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services?f=json",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_CONTOURS/FeatureServer",
        "https://tiles.arcgis.com/tiles/fBc8EJBxQRMcHlei/arcgis/rest/services/DETODEMTilePkg_v2/ImageServer",
    ),
    reason=(
        "raster and vector contours, not landed: decision 35 lands no raster, and decision 54's wave 1 "
        "registers no contours, which are the maintainer's call; checked gives the measured counts"
    ),
)
