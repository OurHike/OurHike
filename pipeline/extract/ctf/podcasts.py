"""Colorado Trail Foundation: podcasts, could not be told (coverage audit 2026-10-01, batch
c7_regional_4).

Not rounded down to NOT_PUBLISHED. Skeptic: still 403 on `/`, `/wp-json/`,
`/category/closures/feed/` and `/traveling-the-ct/alerts/` (curl), and on
`/colorado-trail-foundation/ctf-in-the-news/` (WebFetch). A domain-restricted search finds only one
more guest spot (Backpacker Radio #214, Tisha …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Site 403. A search found only guest appearances on third-party shows ("The Colorado Trail with a named'
        ' individual", 2019; Non-Standard 14er ep. 52, 2024).',
    ),
    where=("https://coloradotrail.org/",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
