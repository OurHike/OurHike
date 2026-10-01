"""National Park Service: places, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Wilderness count is UNKNOWN; the service exists. Skeptic (Measured 2026-10-01): the Wilderness count
still returns HTTP 500 on FeatureServer and MapServer `returnCountOnly`, and on `returnIdsOnly`. The
layer's metadata answers (polygon; `Name`, `Acre_Legis`, `PUBLICDISPLAY`), so the service is up …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2`"
        ' ("NPS Boundary", polygon): 442, `dataLastEditDate` 2026-08-17. Layer 0 is the boundary centroids; '
        "layer 1 is tracts. `.../Wilderness/NPS_Legislated_Wilderness/FeatureServer/0` (polygon): count query "
        "returned HTTP 500 today, as it did for c9. API `/places`: 17,483 (c9).",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2",
        "https://mapservices.nps.gov/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
