"""Trailkeepers of Oregon: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

The miles come from `Shape__Length` divided by 5,280. The layer's spatial reference is EPSG 6557, a
feet-based Oregon Lambert, so the unit is feet (Reasoned). This is a 2022 gap-analysis layer. The
`GAP` rows are road walks, and must not be drawn as trail. No sources.json row covers Oregon apart …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: `https://services3.arcgis.com/3g7oRa9lIIf3eCBb/arcgis/rest/services/OCT_Route/FeatureServer/0` "
        "(ArcGIS, `Admin_TKO`, 204 polylines, data last edited 2022-01-18, no licence text). By `TrailType`: "
        "Existing Route – Beach, 31 segments, ≈175 mi. Existing Route – Trail/Sidewalk, 58, ≈88 mi. GAP "
        "Section, 98, ≈159 mi. GAP Section – Alternative Route, 10, ≈12 mi. Alternate Route, 4, ≈5 mi. GAP "
        "Section (Temporary Gap – Storm Damage), 3, ≈4 mi.",
    ),
    where=("https://services3.arcgis.com/3g7oRa9lIIf3eCBb/arcgis/rest/services/OCT_Route/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
