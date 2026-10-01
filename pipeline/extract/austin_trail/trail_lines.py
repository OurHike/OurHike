"""The Trail Foundation (Austin): trail lines, published, and not landed (coverage audit 2026-10-01,
batch p08_persist).

Licence, TTC layers: `licenseInfo` and `copyrightText` are both empty. Class: none_stated, presumed
reusable under 21(a). Licence, PARD `pard_trails` (`94b29c9c…`): "This product is for informational
purposes and may not have been prepared for or be suitable for legal, engineering, or surveying …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Butler_Trail/FeatureServer/0` (item `12f880fe…`): 237 polylines in PARD's NRPA schema, all "
        '`TRAIL_SYSTEM_NAME` "Ann and Roy Butler Hike and Bike Trail" (`SYSTEM_TYPE` National Designation 143, '
        "Local 55, Local Connector 39). Last edit 2025-03-12. Also: `Butler_Trail_clipped` 278 (2025-02-14); "
        "`trail_route` 248 (2020-09-18); `Pard_trails_RECA` 5 (2026-08-05); `Adjacent_Trails` 227 (OSM-derived,"
        " 2020); `The_Butler_Trail_Mile_Markers` 19 points (2025-03-06); `MileMarkerMap_WFL1`. Upstream "
        "(audit): PARD `pard_trails_nrpa`, 4,096 features. Website: "
        "`wp-json/wp/v2/media?media_type=application` …",
    ),
    where=(
        "https://services7.arcgis.com/X8BO7jvq5nMMymtB/arcgis/rest/services/Butler_Trail/FeatureServer/0",
        "https://thetrailfoundation.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
