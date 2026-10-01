"""New Mexico Volunteers for the Outdoors: challenges, nothing published (coverage audit 2026-10-01,
batch c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav and sitemap.",
        "Skeptic: the 71-URL `page-sitemap.xml` has no programme page. REST searches `challenge` and `patch` "
        'return only work events, e.g. "Spud Patch Trail Backpack".',
    ),
    where=(
        "https://coageo.cabq.gov/cabqgeo/rest/services",
        "https://nmvfo.org/",
    ),
)
