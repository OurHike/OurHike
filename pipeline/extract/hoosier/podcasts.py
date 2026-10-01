"""Hoosier Hikers Council: podcasts, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav, `/documents/`, `/wp-json/`. (Skeptic, 2026-10-01: also `/feed/`, whose 10 items have no "
        'enclosures, `/hoosier-hikers-library/` (documents only), and the iTunes Search API for "Hoosier '
        "Hikers\", which returned 15 shows, none of them HHC's. `/wp-json/wp/v2/categories` returns 404, as the "
        "original found.)",
    ),
    where=("https://hoosierhikerscouncil.org/",),
)
