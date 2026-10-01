"""Natural Bridge Appalachian Trail Club: points of interest, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Shelters overlap ATC's. The features file is the only recent one, and its bridges complement ATC's
`bridges`, which does not reach hikers yet.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`MapData/NBATC_Trail_Features_01.kmz`: 25 points (bridges such as James River Foot Bridge, Pedlar "
        "River Foot Bridge, Rocky Row Run; parking; summits), 2024-07-23. `NBATC_Shelters_000.kml`: 12 shelters"
        " (2013). `NBATC_TrailInfo_002.kml`: 12 points (2013)",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://nbatc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
