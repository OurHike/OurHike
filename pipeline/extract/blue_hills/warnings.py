"""Friends of the Blue Hills: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Hunting is in scope for warnings. This is ArcGIS and current.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'DCR\'s "Blue Hills Hunt Areas", '
        "`https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/HuntAreas_BH_PGC_FM/FeatureServer/18`:"
        ' 13 polygons, YrHuntArea, lastEdit 2026-07-28. Plus "Clipped Wildlife Management Zones". FBH posts '
        'each year on "White-Tailed Deer Management Program 2025" and "Traffic Advisory Related to Controlled '
        'Deer Hunt".',
    ),
    where=("https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/HuntAreas_BH_PGC_FM/FeatureServer/18",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
