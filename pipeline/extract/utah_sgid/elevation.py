"""Utah UGRC — SGID Trails and Pathways: elevation, published as indexes of DEM and contour downloads,
not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. The two layers are tile indexes, each tile a download path, not elevations.

A derivative of the USGS and state lidar the shared elevation source already covers.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `USGS_DEMs_gdb/FeatureServer/0` is 98 polygons and `Contours/FeatureServer/0` "
        "2, both with fields TILE, PATH, EXT, SIZE and TILE_INDEX, edited 2025-09-18: indexes of files to "
        "download, not contour lines or elevations",
        "UGRC redistributes DEMs: `USGS_DEMs_gdb/0` (98-tile index, last edit 2025-09-23), "
        "`AutoCorrelated_DEMs_gdb`, `Contours`.",
    ),
    where=(
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://gis.utah.gov/",
    ),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
