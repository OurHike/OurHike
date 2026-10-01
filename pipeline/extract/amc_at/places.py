"""Appalachian Mountain Club (A.T. sections): places, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

The chapter-boundary polygons would let the `sources` mart map each chapter's area.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "ArcGIS `AMC_Properties_and_Landscapes/FeatureServer/0` (9 polygons) and "
        "`AMC_Chapter_Boundaries/FeatureServer/0` (11 polygons, with Web_URL). WP REST `destinations` (30, with"
        " a `location` taxonomy). The White Mountain Hiker Shuttle page `https://www.outdoors.org/shuttle/` "
        "lists trailhead stops.",
    ),
    where=(
        "https://www.outdoors.org/shuttle/",
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services/AMC_Properties_and_Landscapes/FeatureServer/0",
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services/AMC_Chapter_Boundaries/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
