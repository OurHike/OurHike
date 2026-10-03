"""US Army Corps of Engineers: challenges, nothing published (coverage audit 2026-10-01, batch
c9_federal_state_rest).

A geocache series is a list of places, so it could be a challenge. Nobody could read whether it has
a completion reward. The cache coordinates very likely live on geocaching.com (Unvalidated), whose
terms would be a separate maintainer question. This stays UNKNOWN until the page is read.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Searched `usace.army.mil` for passport and hiking-challenge programs and found only annual day-use "
        "passes. The skeptic's search found a district-run place series instead: St. Louis District, "
        "`https://www.mvs.usace.army.mil/Missions/Recreation/Carlyle-Lake/Recreation/Geocaching/`, described in"
        ' search as "10 Corps of Engineers managed geocaches hidden around Carlyle Lake". J. Strom Thurmond '
        "Lake runs one too (search). The page answers HTTP 403 to curl and to WebFetch. A Wayback snapshot "
        "exists (2026-06-08), but the proxy reset the connection to web.archive.org.",
    ),
    where=(
        "https://www.mvs.usace.army.mil/Missions/Recreation/Carlyle-Lake/Recreation/Geocaching/",
        "https://web.archive.org",
        "https://geocaching.com",
    ),
)
