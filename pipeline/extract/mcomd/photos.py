"""Mountain Club of Maryland: photos, nothing published (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

`/resources/terms/` is a participant waiver for club activities. It does not gate reading the site
(Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/news/gallery/` (club galleries). `/resources/terms/` grants MCM rights over participants' likeness, "
        "not an open licence. Maryland State Archives scrapbooks 1934–1954 are club history, not features",
    ),
    where=("https://mcomd.org/",),
)
