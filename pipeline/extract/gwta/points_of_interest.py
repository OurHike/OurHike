"""Great Western Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch p01_persist).

Licence: none_stated (`licenseInfo` empty on all three ASP items). Reasoned: the layer is named
`gis_osm_pois_free_1` and carries Geofabrik's OSM `code`/`fclass` schema. 452 rows have a non-blank
`fclass`, so those rows are OpenStreetMap-derived and carry ODbL obligations whatever the item says.
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services2.arcgis.com/gdcQ6sUWKP8qwBmV/arcgis/rest/services/GWT_Points_Public_View/FeatureServer/0`"
        ' (item `14a79b43…`, an Arizona State Parks staff account, snippet "Points of interest along the Great '
        'Western Trail in Arizona"). 1,415 points, last edit 2022-12-22. `POI_Type`:',
        "Food and Drink 489, Fuel 133, Lodging 26, Healthcare 21",
        "Wash/Stream Crossing 423",
        "Attraction 99, Camping 79, Staging Area 62, Picnic Site 33, Park 29",
        "Toilet 9, Viewpoint 6, Information 4; Companion `GWT_Alignment_Public_View/0`: 30 lines with `Season` "
        "(Always 10, 3Season 5), last edit 2026-03-20.; On …",
    ),
    where=("https://services2.arcgis.com/gdcQ6sUWKP8qwBmV/arcgis/rest/services/GWT_Points_Public_View/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
