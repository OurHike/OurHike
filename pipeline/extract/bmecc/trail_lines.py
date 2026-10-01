"""Blue Mountain Eagle Climbing Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c2_at_clubs_mid).

The map says it is "not intended for navigation purposes". It duplicates ATC's centerline, so its
only use is as a cross-check.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'via atc `centerline`/`trail_club_sections`. Own geometry: Google My Maps "BMECC Trail Section", KML '
        "export `https://www.google.com/maps/d/kml?mid=1AhhnnzcYgmH6WVNvJeqcjtgiZRgSd8wg&forcekml=1` (1.5 MB): "
        '3 LineStrings (Northern Section, Southern Section, "Appalachian Trail - Pennsylvania")',
    ),
    where=("https://www.google.com/maps/d/kml?mid=1AhhnnzcYgmH6WVNvJeqcjtgiZRgSd8wg&forcekml=1",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
