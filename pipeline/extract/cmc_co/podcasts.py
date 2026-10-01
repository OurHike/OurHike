"""Colorado Mountain Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Nav (YouTube only). WebSearch for "Colorado Mountain Club" podcast found none of CMC\'s own. (Skeptic: '
        'the iTunes Search API for "Colorado Mountain Club" returned 15 shows on 2026-10-01, none published by '
        "CMC.)",
    ),
    where=("https://cmc.org/",),
)
