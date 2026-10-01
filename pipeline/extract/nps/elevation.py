"""National Park Service: elevation, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Park by park, and mostly derived from USGS or NGS lidar, so 3DEP (`_shared/usgs`) stays the better
source and none of this is worth loading first. GRSM's contours are the only ones found on the A.T.
corridor. A note saying "NPS publishes no elevation" would have been false.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
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
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
