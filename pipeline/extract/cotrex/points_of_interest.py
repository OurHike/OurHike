"""Colorado Parks & Wildlife — COTREX: points of interest, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

The trailheads go to `_shared/cotrex`; the facilities stay in `cpw/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`CPWAdminData/0` "CPW Facilities": 5,520 (Parking 1,831, Restroom 643, Campground 262, Campsite 146, '
        "Scenic Overlook 51, Drinking Water 45, Cabin 35…). `/14` COTREX Trailheads: 2,585, with `bathrooms`, "
        "`water`, `fee`. Both last edited 2026-08-27.",
    ),
    where=(
        "https://ndismaps.nrel.colostate.edu/arcgis/rest/services",
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services",
        "https://trails.colorado.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
