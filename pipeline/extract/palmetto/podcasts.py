"""Palmetto Conservation Foundation: podcasts, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Skeptic: a web search finds only guest appearances on other people's shows: South Carolina Public
Radio's "South Carolina Business Review", 2026-05-27 ("Palmetto Trail now over 80% complete", a
named individual), and "The Trail Show" #97. Verdict stands. (R)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Nav and sitemap checked. "Trail Talk" is an event category.',),
    where=("https://palmettoconservation.org/",),
)
