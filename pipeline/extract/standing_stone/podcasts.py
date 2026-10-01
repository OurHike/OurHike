"""Standing Stone Trail Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'No club show. Third party: "Completing the Standing Stone Trail", Younger Old Man (2021-09-22).',
        "Skeptic: none of the 42 pages and 38 blog posts in the sitemaps (posts 2014–2021) is audio. "
        "`/stories-from-the-trail` holds a PDF story and a Relive video link. The Apple directory searched by "
        '"Standing Stone Trail" has no club show.',
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://standingstonetrail.org/",
    ),
)
