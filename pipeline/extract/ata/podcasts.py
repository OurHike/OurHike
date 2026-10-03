"""Arizona Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

Skeptic, kept NOT_PUBLISHED: WordPress REST `search=podcast` returns 10 hits. Every podcast among
them is a guest appearance: OEM Podcast with a named individual, HIKE Podcast Features the Arizona
Trail, The Trail Show – Podcast #32. None of the 73 categories is a podcast category. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Guest appearances only: HIKE podcast (2019-05-01), The Trail Show (2020-05-26), The Landscape "
        "(2026-08). `/the-trail/videos/` is video.",
    ),
    where=("https://aztrail.org/",),
)
