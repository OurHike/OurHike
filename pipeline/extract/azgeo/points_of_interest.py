"""AZGeo Data Hub: points of interest, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Desert water: the free-text `Type` needs a reviewed mapping before it reaches a card.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/0` AZT Water Source Locations: 312, data edit 2026-05-10. `Type` is free text: creek 41, Spring 31, "
        'Dirt Tank 25, Spigot 10, cache 2, "water from hikers" 1… `/1` Trail Points: 3,041 (Milepost 1,664, '
        "Road Jct 467, Water 162, Trailhead 56, Bridge 13, Campground 10). `/2` Trailheads: 106.",
    ),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://azgeo-open-data-agic.hub.arcgis.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
