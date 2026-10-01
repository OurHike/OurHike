"""Maine Appalachian Trail Club: challenges, nothing published (coverage audit 2026-10-01, batch
c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Nav and the WP page list. The "Volunteer Recognition Program" is for volunteers, not a hiker programme.',
        "Skeptic, 2026-10-01: the 60-page sitemap and a web search; patches are for volunteer hours and maintainers only.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://matc.org/",
    ),
)
