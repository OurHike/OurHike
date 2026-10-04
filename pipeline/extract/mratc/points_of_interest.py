"""Mount Rogers Appalachian Trail Club: points of interest, published with no coordinate, and not landed
(decision 54, wave 5, read live 2026-10-04).

The club's backpacking-rules page lists its shelters and campsites with miles north of Damascus, the trail
each is on, and bear box and privy yes or no, and no coordinate. A HIKER'S SAFETY: three of them are on the Iron
Mountain Trail, in neither ATC's shelter layer nor USFS's `usfs_rec_sites` by name (the coverage audit,
2026-10-01): Sandy Flats Campsite (8.2 mi; bear box no, privy yes), Straight Branch Shelter (13.2 mi; no, no)
and Cherry Tree Shelter (19 mi; no, yes). Cherry Tree is named on the 2026 official A.T. detour (MRATC's home
page, the coverage audit), so hikers on the detour pass shelters the map does not show. A point is never looked
up from a name; needs a per-site reader, not built in this pull request, and a fix for each that a person
reviews.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Wix's: `Allow: /`, `Disallow: *?lightbox=`, no Crawl-delay for our agent), then "
        "/backpacking-rules, read 2026-10-04 under lib/user_agent.py's agent: 200, 895,241 bytes. Its "
        "'Shelter/Campsite Info' list, 'Location + Miles north of Damascus + Trail', from 'Sandy Flats Campsite - "
        "8.2 mi - I.M.T. Bearbox - No; Privy - Yes' to 'Trimpi Shelter - 53.6 mi - A.T.'; no coordinate, decimal "
        "or DDM, in the page.",
        "the coverage audit (2026-10-01, batch c3_at_clubs_south): ATC code 25 holds shelters 7 and campsites 5; "
        "the three I.M.T. sites are not in ATC's shelters layer nor in usfs_rec_sites by name.",
    ),
    where=("https://www.mratc.org/backpacking-rules",),
    reason="needs a per-site reader, not built in this pull request: the shelter list gives miles from Damascus and no coordinate",
)
