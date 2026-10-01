"""Rocky Mountain Field Institute: places, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

No licence is stated. These are project sites, so their value for hikers is low.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Google My Maps KML `https://www.google.com/maps/d/kml?mid=1JYWuK-xRDI4gA8zuREE894PcnZEtMUk&forcekml=1`"
        ' (14,475 bytes): 46 points in one folder, "RMFI Project Past, Present and Ongoing" (Garden of the '
        "Gods, Pikes Peak, Red Rock Canyon Open Space …). (Skeptic spot-check, 2026-10-01: again 14,475 bytes "
        "and 46 `<Placemark>`s.)",
    ),
    where=("https://www.google.com/maps/d/kml?mid=1JYWuK-xRDI4gA8zuREE894PcnZEtMUk&forcekml=1",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
