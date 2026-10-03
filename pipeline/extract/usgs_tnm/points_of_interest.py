"""USGS — The National Map: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c9_federal_state_rest).

A GNIS spring is a name on a map, not a report of water. If it ever reaches the water card, it must
render as "named spring, flow unknown". It can never be a confirmed source (CLAUDE.md: "never let a
display outrun its source").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`carto.nationalmap.gov/.../structures/MapServer`: Trailheads (26) 13,389; Campgrounds (25) 7,748; "
        "Ranger Stations (32) 891; Cabins (27) 589; Shelters (28) 30. GNIS `geonames/MapServer/7` with "
        "`gaz_featureclass='Spring'`: 34,885 springs.",
    ),
    where=(
        "https://earthquake.usgs.gov/arcgis/rest/services",
        "https://partnerships.nationalmap.gov/arcgis/rest/services",
        "https://usgs.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
