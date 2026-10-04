"""Palmetto Conservation Foundation: places. The passage pages the coverage audit read as a trailhead directory
are loaded as points of interest, in palmetto/points_of_interest.py (`palmetto_trail_passages`): a trailhead
or a parking area is a point, not an area (decision 54, wave 5, read 2026-10-04).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "The 33 passage pages the sitemap lists under https://www.palmettotrail.org/trails/trail/, read "
        "2026-10-04: each plots typed markers (Parking 72, Trail Head 52, Visitor Center 7 among 363) and its "
        "passage line, and names the passage in its <h1>; registered as `palmetto_trail_passages`. No passage "
        "page draws an area: the line is the passage, and the coverage audit's Region field (Upstate, Midlands, "
        "Lowcountry) is a word on the page, not a boundary (2026-10-01, c7_regional_4).",
    ),
    where=("https://www.palmettotrail.org/trails/trail/awendaw-passage",),
    reason="loaded as points of interest and trail lines: the passages' trailheads are points, in points_of_interest.py",
)
