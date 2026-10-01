"""Potomac Appalachian Trail Club: points of interest, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

The 14 Tuscarora shelters and the cabins are new to us (ATC's layer covers the A.T. only, Reasoned).
Cabins are under the Council-authorization term. Per the item text, 25 of 42 rentable cabins are
members-only.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`PATC_Shelters_AT_and_TT_2_view/0`: 47 (32 "Official A.T. Shelter", 14 "T.T. Shelter", 1 other; '
        "2024-09-25; food-storage fields, no capacity). `Cabin_Locations/0`: 49 cabins (26 primitive, 14 "
        "modern, 7 semi-primitive; `Capacity`, `Hike_In`, `AT_Access`, costs, booking link; 2026-03-10). "
        "`Cabin_Parking/0` 21 (2020). `Map_9_Revisted_2019_2020_POIs/0` 778 GPS-ranger waypoints (junctions, "
        "crossings, blowdowns, about 28 springs; 2021-11). `Bull_Run_Occoquan_Trail/0` 112. `/shelters` page "
        'lists water facts, e.g. "Charlie Irvin Shelter (no water)"',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://patc.net/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
