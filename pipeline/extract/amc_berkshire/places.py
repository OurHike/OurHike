"""AMC Berkshire Chapter: places. The chapter's one places-shaped page, its A.T. parking areas, is loaded as
points of interest, in amc_berkshire/points_of_interest.py, because a parking area is a point a hiker drives
to, not an area (decision 54, wave 5, read 2026-10-04).

Noble View Outdoor Center is already a point in `amc`'s `AMC_Destinations` (the coverage audit, 2026-10-01).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        '`https://www.amc-wma.org/documents-more.cgi?id=112` "A.T. Parking Areas and Trailhead" (page, '
        "11-Jan-2025), read 2026-10-04: 28 parking areas north to south, 27 with a coordinate, each with "
        "capacity, an overnight grade, winter plowing and a map kiosk. Registered as `amc_wma_at_parking_points` "
        "and extracted in amc_berkshire/points_of_interest.py; no other place, park or town list on amc-wma.org "
        "was found by the coverage audit (2026-10-01, batch c1_at_clubs_north).",
    ),
    where=("https://www.amc-wma.org/documents-more.cgi?id=112",),
    reason="loaded as points of interest: the parking page's areas are points, in the sibling points_of_interest.py",
)
