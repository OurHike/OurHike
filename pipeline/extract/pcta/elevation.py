"""Pacific Crest Trail Association: elevation, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

A 30 m-DEM classification is coarser than the shared USGS source, so there is no reason to load it
as elevation (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`PCT_Per_Thousand_Ft/FeatureServer/0` (14 lines, the PCT classed per 1,000 ft "on 30m DEM", last edit '
        "2024-04-29). `PCT_Corridor_Elevation_Ranges/FeatureServer/0` (14 polygons). `Trips` rows carry "
        "`Gain_ft`/`Loss_ft`.",
    ),
    where=(
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCT_Per_Thousand_Ft/FeatureServer/0",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCT_Corridor_Elevation_Ranges/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
