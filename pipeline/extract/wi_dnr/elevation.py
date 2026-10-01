"""Wisconsin DNR Open Data: elevation, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

A real statewide lidar DEM. Whether it adds anything over the shared USGS elevation source for
Wisconsin is @unvalidated: 3DEP may carry the same county lidar. What would settle it is comparing
the two sources' tile dates and resolutions for one county. Not a club-folder load. If anything, it
is …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
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
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
