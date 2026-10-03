"""Mount Rogers Appalachian Trail Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c3_at_clubs_south).

(skeptic) Agreed; that podcast has one MRATC episode (ep. 7, "a named individual Mt. Rogers ATC",
2019-05-03). See `tehcc` for the `_shared/` recommendation.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Sitemap; iTunes ("Trail Maintainers Podcast" belongs to an individual, not MRATC).',),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://mratc.org/",
    ),
)
