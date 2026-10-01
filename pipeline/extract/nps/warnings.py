"""National Park Service: warnings, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Two alerts bear on water and are not drought: grca "INNER CANYON WATER SHUTOFFS" (Danger) and grfa
"Public restrooms closed … no drinking water". They belong next to the water card, not in warnings
alone. Maintainer call.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Same endpoint, Danger 15 + Caution 107 of the 500. Examples: peco "South Pasture Trail, all River '
        'Access Closed Due to Flood Conditions" (Danger); olym "Crews Responding to Mount Tom Creek Fire"; kefj'
        ' "Canyon from Toe of Exit Glacier to the Outwash Plain". Keyword hits in the 500: fire 29, flood 17, '
        "heat 12, hunt 10, bear 5.",
        "Skeptic adds (Measured 2026-10-01), park layers in the NPS org: "
        "`YOSE_FireRestrictionStages/FeatureServer/0` holds 147 polygons (`RESTRICTSTAGE`, `RESTRICTDESC`), "
        "edited 2026-08-27. `YOSE_RockFall_HazardLine_YosemiteValley/FeatureServer/0` holds 12 lines, edited …",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/YOSE_FireRestrictionStages/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/YOSE_RockFall_HazardLine_YosemiteValley/FeatureServer/0",
        "https://mapservices.nps.gov/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
