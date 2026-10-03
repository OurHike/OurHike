"""North Country Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WordPress search "podcast": 3 hits, none a show.',
        'Skeptic adds: Apple Podcasts search "North Country Trail": 8 shows, none NCTA\'s ("Trail Maintainers '
        'Podcast", "Sounds in the Woods", "MICHIGAN Pathways" are independent).',
    ),
    where=("https://northcountrytrail.org/",),
)
