"""Maine Appalachian Trail Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The A.T. Museum feed is a `_shared/podcasts` lead (see Skeptic pass).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Nav and the WP page list. "MATC Video Library" (`/matc-video-library/`) is video, not audio.',
        "Skeptic, 2026-10-01: the WP sitemap (60 pages, types incl. `tribe_events`, no podcast type) and a web "
        "search. MATC appears as a guest on other people's shows (the Appalachian Trail Museum's \"A.T.rail Of "
        'History"; a senator\'s "Inside Maine"), which are not MATC\'s.',
    ),
    where=("https://matc.org/",),
)
