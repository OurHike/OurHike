"""Ozark Trail Association: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Parking/trailheads. Section pages also give campground rules ("No camping in Peck Ranch").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same KML\'s "Trailhead" folder: 72 points. Each description carries "Elevation = … ft", '
        '"Coordinates = …" and "Type = Trailhead".',
    ),
    where=("https://ozarktrail.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
