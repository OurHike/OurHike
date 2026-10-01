"""Friends of the Blue Hills: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Not LOADED (correction 2). The `ILLEGAL` field needs filtering: R that it marks unofficial paths.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'DCR\'s "Blue Hills Trail Lines (public)", '
        "`https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/BlueHillsTrailLinesPublic/FeatureServer/2`:"
        " 1,630 polylines with NAME, STATUS, TRAIL_MARK, CONDITION, ILLEGAL; lastEdit 2026-07-28. MassGIS "
        "`AGOL/DCR_Roads_and_Trails_Arcs/FeatureServer/0`: 36,859 statewide, not registered. FBH's own: PDFs "
        "`wp/wp-content/uploads/trails/maps/blue-hills-trail-map-2020.pdf` (DCR's map).",
    ),
    where=(
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/BlueHillsTrailLinesPublic/FeatureServer/2",
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/DCR_Roads_and_Trails_Arcs/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
