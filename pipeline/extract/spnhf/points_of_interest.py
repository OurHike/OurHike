"""Society for the Protection of NH Forests: points of interest, published, and not landed (coverage
audit 2026-10-01, batch c4_regional_1).

ArcGIS beats page, but this layer is 6 years stale.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same service: layer 2 "Trailhead" (86 points), layer 3 "Parking" (39), layer 0 "GRANIT Recreation '
        'Inventory Points" (46); last edits 2020-05. Property pages give parking coordinates, e.g. Mount Major '
        "`google.com/maps/dir//43.519272,-71.272742`.",
    ),
    where=("https://google.com/maps/dir//43.519272,-71.272742",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
