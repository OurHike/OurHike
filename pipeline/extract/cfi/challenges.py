"""Colorado Fourteeners Initiative: challenges, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav, sitemap. CMC keeps the 14er completer list. (Skeptic: I read the list of 70 non-peak page URLs in"
        " `wp-sitemap-posts-page-1.xml`, which lists 130 URLs in all, but not the pages themselves. No URL "
        "names a challenge, award or completer page. The nearest are `/where-we-work/adopt-a-peak-crew/` and "
        "`/where-we-work/peak-stewards/`, which are volunteer programmes.)",
    ),
    where=("https://14ers.org/",),
)
