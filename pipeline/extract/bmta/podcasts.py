"""Benton MacKaye Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No podcast in the nav. Apple has no BMTA show. Episodes about the BMT are on third-party shows: Hike, "
        '"Trailblazing the Benton MacKaye Trail with a named individual" (2019-04-24); FKT Podcast '
        "(2024-03-01); n2backpacking Ep. 28 (2015).",
        "Skeptic: none of the 38 pages in `page-sitemap.xml` is a podcast; `/vids/` is video. The Apple "
        'directory searched by "Benton MacKaye" lists 15 shows, none of them the BMTA\'s.',
    ),
    where=("https://bmta.org/",),
)
