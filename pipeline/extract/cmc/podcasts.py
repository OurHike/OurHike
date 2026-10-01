"""Carolina Mountain Club: podcasts, nothing published (coverage audit 2026-10-01, batch
c3_at_clubs_south).

(skeptic) The third-party Trail Maintainers Podcast (see `tehcc`) has four CMC episodes (8, 9, 11
"Carolina Mtn Club NTD on Max Patch", 17). Not CMC's.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WP search "podcast" (the only hit is unrelated); iTunes. A YouTube channel (`@carolinamountainclub2188`) is video.',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://carolinamountainclub.org/",
    ),
)
