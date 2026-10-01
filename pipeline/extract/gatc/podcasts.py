"""Georgia Appalachian Trail Club: podcasts, nothing published (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WP `/search` "podcast" finds only the "A.T. Gateways 2026 Full Schedule" page, which lists a visiting '
        '"Podcaster a named individual". "audio" finds 0. No `<enclosure>` in the news, alerts or events feeds.',
    ),
    where=("https://georgia-atclub.org/",),
)
