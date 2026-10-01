"""Potomac Appalachian Trail Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Checked the sitemap (444 URLs) and the 257 RSS items: every "podcast" mention is a third-party show. '
        "YouTube `UCL6pQSSl5z4xXER8xD-3hRg` holds webinars (video)",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://patc.net/",
    ),
)
