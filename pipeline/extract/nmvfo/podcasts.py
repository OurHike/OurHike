"""New Mexico Volunteers for the Outdoors: podcasts, nothing published (coverage audit 2026-10-01,
batch c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav and sitemap.",
        "Skeptic: REST search `podcast` returns 0. The Apple directory for the org's name returns 8 shows, none of them NMVFO's.",
    ),
    where=(
        "https://coageo.cabq.gov/cabqgeo/rest/services",
        "https://nmvfo.org/",
    ),
)
