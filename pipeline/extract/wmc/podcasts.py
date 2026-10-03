"""Wasatch Mountain Club: podcasts, nothing published (coverage audit 2026-10-01, batch c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav. There is a YouTube video and an mp4 club-history file. (Skeptic, 2026-10-01: the sitemap has 940 "
        "`/rambler/…` URLs. The Rambler is the club's newsletter, which is text, not audio. The iTunes Search "
        'API for "Wasatch Mountain Club" returned 15 shows, none of them WMC\'s. The nearest are the Utah '
        "Avalanche Center's and Wasatch Backcountry Alliance's \"The Uptrack\".)",
    ),
    where=("https://wasatchmountainclub.org/",),
)
