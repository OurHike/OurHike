"""Wasatch Mountain Club: places, published, and not landed (coverage audit 2026-10-01, batch
p08_persist).

Licence: UGRC is none_stated (a disclaimer). Folder: `_shared/utah_ugrc`. Millcreek City's "Local
Parks" item (`5822068b…`) opens "This layer is provided for general public information, recreation
reference, and map context. It is not an official o…"; I read only that much of it. UGRC already …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "In the box: UGRC `UtahParksLocal/0` 644 polygons, `UtahMunicipalBoundaries/0` 28, "
        "`state_park_boundaries_dissolved/0` 5, and `UtahWildernessAreas/0` 3 (Lone Peak, Mount Olympus, Twin "
        "Peaks; `Admin` USFS). b7 has the statewide counts. The WMC Lodge stays one place, not a dataset. "
        "Tried: 1, 2, 3, 4 (`EDW_Wilderness_02` has the same three wildernesses), 5.",
    ),
    where=(
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://wasatchmountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
