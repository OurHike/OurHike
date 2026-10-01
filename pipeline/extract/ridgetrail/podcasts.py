"""Bay Area Ridge Trail Council: podcasts, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "REST search `podcast` returns one blog post.",
        'Skeptic: the Apple directory for "Bay Area Ridge Trail" and "Ridge Trail Council" returns 16 shows, '
        "none of them the Council's.",
    ),
    where=(
        "https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services",
        "https://ridgetrail.org/",
    ),
)
