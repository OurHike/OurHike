"""National Park Service: places, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

The boundary service sits in the same ArcGIS org that hosts ATC's `ANST_` layers.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`services1.arcgis.com/fBc8EJBxQRMcHlei/.../NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2`"
        " (NPS Boundary, 442 polygons). API `/places`: 17,483. `Wilderness/NPS_Legislated_Wilderness` exists, "
        "but its count query returned HTTP 500.",
    ),
    where=("https://nps.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
