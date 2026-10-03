"""AMC Berkshire Chapter: podcasts, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nav and sitemap (495 URLs; none podcast-shaped).",
        'Skeptic, 2026-10-01: the iTunes Search API for "Appalachian Mountain Club" returns no chapter show.',
    ),
    where=(
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://amcberkshire.org/",
    ),
)
