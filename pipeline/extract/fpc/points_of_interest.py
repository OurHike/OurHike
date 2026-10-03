"""Forest Park Conservancy: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

KML is machine-readable. The page also describes the Wildwood's quarter-mile blue blazes and Leif
Erikson's white mile posts, which are useful wayfinding text.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Google My Maps "Forest Park Trailheads", mid `1lykYs7fUx9AXn8VZlywlQGo-8fmYJHQ`, embedded on '
        "`/forest-park/maps/`. KML export "
        "`https://www.google.com/maps/d/kml?mid=1lykYs7fUx9AXn8VZlywlQGo-8fmYJHQ&forcekml=1` (30,745 bytes): 19"
        ' placemarks, e.g. "Thurman: Leif Erikson Drive", "Germantown: Wildwood Trail", "Newberry Road".',
    ),
    where=(
        "https://www.google.com/maps/d/kml?mid=1lykYs7fUx9AXn8VZlywlQGo-8fmYJHQ&forcekml=1",
        "https://forestparkconservancy.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
