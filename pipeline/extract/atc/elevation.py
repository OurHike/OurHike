"""ATC publishes Z on one centerline layer, which is not landed yet.

What ships as elevation is USGS 3DEP (_shared/usgs/). ATC's ATX Ratings
centerline carries Z, and its value here would be a cross-check against 3DEP,
not a profile a hiker sees (ORG_COVERAGE_SURVEY.md, batch b1_atc). A builder
takes a registered key, so this becomes a resource once that layer has a
sources.json row.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "ATX_Ratings/FeatureServer/9 (and 1, 5, 10), 'Centerline Current': hasZ true, 697 polylines, last edited "
        "2025-10-01; one sampled feature (Baxter Peak to Katahdin Stream Campground) has Z from 330.5 to 1,601.6 m",
        "ANST_Centerline/FeatureServer/0, the centerline that ships: hasZ false",
        "the half-mile points: fields Name, Point_ID, Measure, MeasureM, no elevation",
        "the A.T. Data Book's elevations: a sold product",
    ),
    where=(
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/ATX_Ratings/FeatureServer/9",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Centerline/FeatureServer/0",
    ),
    reason="published with Z, and not landed: the layer has no sources.json row, which a builder needs",
)
