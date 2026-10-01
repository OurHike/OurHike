"""Forest Park Conservancy: places, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Low value: one polygon for a preserve that is not Forest Park itself.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"GFP FPC Ancient Forest Preserve Boundary", '
        "`TNC_CRS_GFP_Ancient_Forest_Preserve_Boundary/FeatureServer/0` (1 polygon, 2020-10-19). There are also"
        " pages for Forest Park and Marquam Nature Park.",
    ),
    where=(
        "https://services2.arcgis.com/bTtaWPOlNeue1hk7/arcgis/rest/services/TNC_CRS_GFP_Ancient_Forest_Preserve_Boundary/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
