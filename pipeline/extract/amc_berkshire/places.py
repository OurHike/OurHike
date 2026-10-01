"""AMC Berkshire Chapter: places, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Parking is also a `points_of_interest` type. 25 entries write "Lat/Lon:" and 1 writes "Lat.Lon:", so
a parser must accept both. Noble View Outdoor Center is already a point in `amc`'s
`AMC_Destinations`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.amc-wma.org/documents-more.cgi?id=112` "A.T. Parking Areas and Trailhead" (page, '
        '11-Jan-2025): A.T. parking areas listed north to south, with 29 "Capacity" figures and 26 coordinate '
        'pairs (a few day-use pull-offs have no coordinates). An entry gives `Lat/Lon` in the text (e.g. "Rt 2,'
        " North Adams … Capacity: 8 vehicles … Plowed in winter. Suitable for overnight parking. Map kiosk: no."
        ' Lat/Lon: 42.69936, -73.15358"), capacity, winter plowing, an overnight-safety grade (Suitable / Short'
        " term / Not recommended / Day use) and whether there is a map kiosk.",
    ),
    where=("https://www.amc-wma.org/documents-more.cgi?id=112",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
