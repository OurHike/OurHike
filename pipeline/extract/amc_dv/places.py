"""AMC Delaware Valley Chapter: places, gone: the trailhead KML its page links answers 404 (decision 54,
wave 2, read 2026-10-04).

`/leadership/trailheads/` still links `/assets/hikeparking.kml`, which answered 404 on 2026-10-04 as it
did for the coverage audit (2026-10-01). The page itself gives Google Maps coordinate links for state-
park trailheads in DE, NJ and PA, an HTML page and so wave 5's (a reader per site). Marginal, and mostly
off the A.T.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://amcdv.org/assets/hikeparking.kml: HEAD 404, 2026-10-04, under lib/user_agent.py's agent (robots.txt read first, no rule against it).",
        "https://amcdv.org/leadership/trailheads/, read 2026-10-04: the page still links that file, and its trailheads are Google Maps coordinate links in HTML.",
    ),
    where=(
        "https://amcdv.org/assets/hikeparking.kml",
        "https://amcdv.org/leadership/trailheads/",
    ),
    reason="gone: the one GIS file is a 404; the trailhead page is HTML, wave 5's (a reader per site)",
)
