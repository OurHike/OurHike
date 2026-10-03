"""New York–New Jersey Trail Conference: podcasts, nothing published (coverage audit 2026-10-01, batch
b2_nynjtc).

Kaatscast is a named individual Catskills podcast, not NYNJTC's, so it is a `_shared/` podcast
candidate. The Trail Talks videos would fit a podcast mart only if the mart accepts video, which is
a design call this audit does not make.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "• WP `/search?search=podcast` returns 2 unrelated hits (a conservation-dogs page and an ultrarunner news post).",
        "`/trail-talks-webinar-series/` (2026-04-21) embeds 10 YouTube videos, not audio.",
        "`/wp-json/wp/v2/types` shows no podcast or episode post type.",
        'WebSearch for `"New York-New Jersey Trail Conference" podcast` finds only Kaatscast\'s third-party '
        'episode "More than Maps: New York - New Jersey Trail Conference" (recorded 2024-09-24, '
        "https://www.kaatscast.com/more-than-maps-new-york-new-jersey-trail-conference/).; Skeptic recheck, "
        "verdict upheld (Measured 2026-10-01):",
        "The Apple …",
    ),
    where=(
        "https://www.kaatscast.com/more-than-maps-new-york-new-jersey-trail-conference/",
        "https://nynjtc.org/",
    ),
)
