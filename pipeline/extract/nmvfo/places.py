"""New Mexico Volunteers for the Outdoors: places, published, and not landed (coverage audit
2026-10-01, batch p05_persist).

USFS: public domain. RGIS `useconst`: "This data shall not be used to define legal boundaries of
State Parks, nor to define the limits of jurisdiction or ownership between adjacent property owners.
Use of this data implies authors' release from liability as to accuracy of data." `accconst`: "No …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "USFS `EDW_ForestSystemBoundaries_01/MapServer/0`: Cibola (0303, 3,215,660 acres), Santa Fe (0310) and "
        "Lincoln (0308). `EDW_Wilderness_02`: Sandia Mountain Wilderness (37,690 acres) and Pecos Wilderness "
        "(221,836 acres). NM State Parks boundaries: RGIS GStoRE dataset "
        '`057d2f19-4ec6-47d5-82a4-f03309ef94fb`, "New Mexico State Parks / State Park boundaries", last updated'
        " 2025-01-22, served as GeoJSON, shapefile, KML and CSV. I did not count its features, because it is "
        "download-only. City of Albuquerque "
        "`https://coageo.cabq.gov/cabqgeo/rest/services/agis/Open_Space/FeatureServer/0`: 65 polygons. …",
    ),
    where=("https://coageo.cabq.gov/cabqgeo/rest/services/agis/Open_Space/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
