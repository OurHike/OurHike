"""Finger Lakes Trail Conference: places, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic spot-check: `FLT_Index_Rectangles` holds 54 polygons, lastEdit 2026-04-06.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Waypoints `PostOffices` (27, resupply towns). `FLT_Index_Rectangles/FeatureServer/6` (map-sheet "
        "polygons). `/plan-hikes-finger-lakes-trail/parks/`.",
    ),
    where=(
        "https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/FLT_Index_Rectangles/FeatureServer/6",
        "https://fingerlakestrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
