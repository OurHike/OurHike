"""Palmetto Conservation Foundation: challenges, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Skeptic re-check: `sitemap.xml` has 74 URLs. I read the non-passage pages among them
(`/about/the-palmetto-trail`, `/hiking-101`, `/updates/post/from-the-mountains-to-the-sea`), and
none carries a completion programme. A "Palmetto Thru-Hiker" definition ("within a 60-day period")
and a "Palmetto …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'No completion programme. Accounts get a personal "Trail Log" and wish list, and `#finishthetrail` is a campaign tag.',
    ),
    where=("https://palmettoconservation.org/",),
)
