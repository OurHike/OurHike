"""Central Iowa Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01,
batch p02_persist).

Licence: Des Moines: explicit_restriction: "© Copyright City of Des Moines, Iowa 2025. All rights
reserved. Disclaimer: The data is provided for reference only…". Iowa DNR: none_stated (empty
`licenseInfo` and `copyrightText`; `accessInformation` "Iowa Department of Natural Resources").
Johnston: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Des Moines Area Regional GIS Partnership / City of Des Moines Trails: "
        "`https://services.arcgis.com/HT7H9QGiZQoRJDpJ/arcgis/rest/services/Trails_view/FeatureServer/0` (item "
        "`758972248b7b47cf8891dee2b429c4cd`; also published as Shapefile, GeoJSON, CSV and FGDB items). 4,924 "
        "polylines, last edit 2026-09-04; `SurfaceType='Earthen'` 215 segments, 40.2 mi. CITA areas by name: "
        "Ewing Park (Nature Trails, Nature Trail, Flow Trail) 51 segments / 7.14 mi. Grandview Park Nature "
        'Trail 4 / 1.44 mi. "Center and Denmans" 32 / 9.95 mi. Sycamore (Sycamore Access, Sycamore North, Top '
        "Shelf, Owl Trail, Lake …",
    ),
    where=(
        "https://services.arcgis.com/HT7H9QGiZQoRJDpJ/arcgis/rest/services/Trails_view/FeatureServer/0",
        "https://programs.iowadnr.gov/geospatial/rest/services/Recreation/State_Parks_trails_view/MapServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
