"""Green Mountain Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The verdict holds. The `_shared/podcasts` lead is VPR's audio, not GMC's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No GMC podcast. `/sounds-and-stories-on-the-long-trail/` (2026-04-20) is a guest post about a third "
        'party\'s audio documentary ("Field Notes: A Long Trail Odyssey"). "Podcasts from the Past" at '
        "`gmcburlington.org` belongs to a GMC section (Burlington), not the club.",
        "Skeptic, 2026-10-01: that page is a list of links to other people's audio: Vermont Public Radio's "
        '"Trail Markers" (2010) and "The Long Trail: Vermont\'s Footpath Through History", plus Vermont History '
        "Museum material (per web search). The section's site answers HTTP 202 with a SiteGround bot challenge "
        "(`sg-captcha: challenge`), so …",
    ),
    where=(
        "https://gmcburlington.org",
        "https://greenmountainclub.org/",
    ),
)
