"""Colorado Fourteeners Initiative: podcasts, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav, `wp-json`, `/feed/` (10 posts, newest 2025-12-23). An episode about CFI exists on Studio 809, but"
        " that is a third party's podcast. (Skeptic, 2026-10-01: `/wp-json/wp/v2/categories` has 7 categories "
        "(blog 200, photo detail gallery 23, Videos detail gallery 19 …) and no podcast or audio category. The "
        'iTunes Search API for "Fourteeners" found no CFI show.)',
    ),
    where=("https://14ers.org/",),
)
