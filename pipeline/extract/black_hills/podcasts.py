"""Black Hills Trails: podcasts, nothing published (coverage audit 2026-10-01, batch c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Nav, `wp-json` namespaces. (Skeptic: the iTunes Search API for "Black Hills Trails" returned 15 shows,'
        " none of them this org's.)",
    ),
    where=("https://blackhillstrails.org/",),
)
