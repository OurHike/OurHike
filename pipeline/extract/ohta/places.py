"""Ozark Highlands Trail Association: places. The trail page's 41 major trailheads are loaded as points of
interest, in ohta/points_of_interest.py (`ohta_major_trailheads`), each with the segment it is listed under;
the four segments themselves are names and lengths in prose, with no area (decision 54, wave 5, read
2026-10-04).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://ozarkhighlandstrail.com/wp-json/wp/v2/pages/15, the trail page through its REST route, read "
        "2026-10-04 (modified 2026-09-10): four segment headings, BOSTON MOUNTAINS, BUFFALO RIVER, SYLAMORE and "
        "NORFORK LAKE, each with prose and a 'Major trail heads' list of fixes; registered as "
        "`ohta_major_trailheads`, which lands each segment's name on its trailheads. The segments' lengths "
        "(Boston Mountains 164 mi, Buffalo River 43, Sylamore 32, Norfork Lake 72, the coverage audit's reading "
        "of 2026-10-01) are sentences, and no segment is drawn as an area anywhere on the site.",
    ),
    where=("https://ozarkhighlandstrail.com/trail/",),
    reason="loaded as points of interest: the segments' trailheads are points, in points_of_interest.py",
)
